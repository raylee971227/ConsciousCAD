from __future__ import print_function
import time
from flask import Flask, request, jsonify, render_template

import os
from dotenv import load_dotenv
import sys
import torch
import io
import numpy as np
from PIL import Image
import torch.onnx
from datetime import datetime
from torch.autograd import Variable
from AttnGAN.code.miscc.config import cfg, cfg_from_file
from AttnGAN.code.miscc.utils import build_super_images2
from AttnGAN.code.model import RNN_ENCODER, G_NET
from werkzeug.contrib.cache import SimpleCache
import pickle
import json
import logging 
import boto3
from botocore.exceptions import ClientError

cache = SimpleCache()

app = Flask(__name__)

load_dotenv(os.path.join(os.getcwd(), '.env'))
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

def vectorize_caption(wordtoix, caption, copies=2):
    # create caption vector
    tokens = caption.split(' ')
    cap_v = []
    for t in tokens:
        t = t.strip().encode('ascii', 'ignore').decode('ascii')
        if len(t) > 0 and t in wordtoix:
            cap_v.append(wordtoix[t])

    # expected state for single generation
    captions = np.zeros((copies, len(cap_v)))
    for i in range(copies):
        captions[i,:] = np.array(cap_v)
    cap_lens = np.zeros(copies) + len(cap_v)

    #print(captions.astype(int), cap_lens.astype(int))
    #captions, cap_lens = np.array([cap_v, cap_v]), np.array([len(cap_v), len(cap_v)])
    #print(captions, cap_lens)
    #return captions, cap_lens

    return captions.astype(int), cap_lens.astype(int)


def word_index():
    ixtoword = cache.get('ixtoword')
    wordtoix = cache.get('wordtoix')
    if ixtoword is None or wordtoix is None:
        #print("ix and word not cached")
        # load word to index dictionary
        x = pickle.load(open('AttnGAN/data/plans2/captions.pickle', 'rb'))
        ixtoword = x[2]
        wordtoix = x[3]
        del x
        cache.set('ixtoword', ixtoword, timeout=60 * 60 * 24)
        cache.set('wordtoix', wordtoix, timeout=60 * 60 * 24)

    return wordtoix, ixtoword

def models(word_len):
    cfg_from_file('./AttnGAN/code/cfg/eval_plans2.yaml')
    text_encoder = cache.get('text_encoder')
    if text_encoder is None:
        #print("text_encoder not cached")
        text_encoder = RNN_ENCODER(word_len, nhidden=cfg.TEXT.EMBEDDING_DIM)
        state_dict = torch.load(cfg.TRAIN.NET_E, map_location=lambda storage, loc: storage)
        text_encoder.load_state_dict(state_dict)
        if cfg.CUDA:
            text_encoder.cuda()
        text_encoder.eval()
        cache.set('text_encoder', text_encoder, timeout=60 * 60 * 24)

    netG = cache.get('netG')
    if netG is None:
        #print("netG not cached")
        netG = G_NET()
        state_dict = torch.load(cfg.TRAIN.NET_G, map_location=lambda storage, loc: storage)
        netG.load_state_dict(state_dict)
        if cfg.CUDA:
            netG.cuda()
        netG.eval()
        cache.set('netG', netG, timeout=60 * 60 * 24)

    return text_encoder, netG

# def upload_image(file, bucket, object_name=None):
# 	if object_name == None:
# 		object_name = file

# 	client_s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)

# 	in_mem_file = io.BytesIO()
# 	pil_image = Image.open(file)
# 	pil_image.save(in_mem_file, format='png')
# 	in_mem_file.seek(0)

# 	try:
# 		client_s3.upload_fileobj(in_mem_file, bucket, object_name, ExtraArgs={'ACL': 'public-read'})
# 		url = "https://{}.s3.amazonaws.com/{}".format(bucket, file)
		
#         return

# 	except ClientError as e:
# 		logging.error(e)
# 		return None 


def generate(caption, wordtoix, ixtoword, text_encoder, netG, copies=2):
    # load word vector
    captions, cap_lens  = vectorize_caption(wordtoix, caption, copies)
    n_words = len(wordtoix)

    # only one to generate
    batch_size = captions.shape[0]

    nz = cfg.GAN.Z_DIM
    captions = Variable(torch.from_numpy(captions), volatile=True)
    cap_lens = Variable(torch.from_numpy(cap_lens), volatile=True)
    noise = Variable(torch.FloatTensor(batch_size, nz), volatile=True)

    if cfg.CUDA:
        captions = captions.cuda()
        cap_lens = cap_lens.cuda()
        noise = noise.cuda()

    #######################################################
    # (1) Extract text embeddings
    #######################################################
    hidden = text_encoder.init_hidden(batch_size)
    words_embs, sent_emb = text_encoder(captions, cap_lens, hidden)
    mask = (captions == 0)

    #######################################################
    # (2) Generate fake images
    #######################################################
    noise.data.normal_(0, 1)
    fake_imgs, attention_maps, _, _ = netG(noise, sent_emb, words_embs, mask)

    # G attention
    cap_lens_np = cap_lens.cpu().data.numpy()

    prefix = datetime.now().strftime('%Y/%B/%d/%H_%M_%S_%f')
    urls = []

    for j in range(batch_size): #1
        for k in range(len(fake_imgs)):
            im = fake_imgs[k][j].data.cpu().numpy()
            im = (im + 1.0) * 127.5
            im = im.astype(np.uint8)
            im = np.transpose(im, (1, 2, 0))
            im = Image.fromarray(im)

            # save image to stream
            stream = io.BytesIO()
            im.save(stream, format="png")
            stream.seek(0)

            filename = '%s/%s_g%d.png' % (prefix, "plans", k)

            # Upload image to s3
            client_s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
            try:
                client_s3.upload_fileobj(stream, AWS_BUCKET_NAME, filename, ExtraArgs={'ACL': 'public-read'})
                url = "https://{}.s3.amazonaws.com/{}".format(AWS_BUCKET_NAME, filename)
                
                urls.append(url)

            except ClientError as e:
                logging.error(e)
                return None 

        if copies == 2:
            break
    
    return urls


def eval(caption):
    # load word dictionaries
    wordtoix, ixtoword = word_index()
    # lead models
    text_encoder, netG = models(len(wordtoix))
    urls = generate(caption, wordtoix, ixtoword, text_encoder, netG)

    # response = {urls}
    print(urls)
    return urls
@app.route('/', methods=["GET"])
def home():
    return render_template("index.html", flask_token="home")


@app.route('/time')
def get_current_time():
    return {'time': time.time()}

@app.route('/generate', methods=["POST"])
def gen_plan():
    data = request.get_json()
    caption = data.get('caption')
    url = eval(caption)
    json_return = jsonify(url)
    return json_return

if __name__ == "__main__":
    app.run()