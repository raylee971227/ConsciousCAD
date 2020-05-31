# unpickle.py
# Raymond Lee
# file to unpickle .pickle files to see what the fuck is going on 


import os
import sys
import argparse
import pickle 
import pprint


def parse_args():
	parser = argparse.ArgumentParser(description='unpickles file to readable object format')
	parser.add_argument('--src', dest='src')
	parser.add_argument('--dest', dest='dest', default='../data/')
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	args = parse_args()
	source_file = args.src
	dest_file = args.dest

	pickle_file = open(source_file, 'rb')
	data = pickle.load(pickle_file)
	pickle_file.close()

	# output_file = open(dest_file, "w")

	for line in data:
		# output_file.write("{}\n".format(line))
		print(line)

	# output_file.close()

