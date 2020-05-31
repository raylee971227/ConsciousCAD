import React from 'react';
import axios from 'axios'
import './App.css';
import logo from './consciouscad_logo.png'
import mainphoto from './main.png'
require('dotenv').config()

class App extends React.Component {
  constructor() {
    super()
    this.state ={
      caption: ""
    }
    this.handleChange = this.handleChange.bind(this);
    this.handleSubmit = this.handleSubmit.bind(this);
  }
  handleChange(event) {
    this.setState({
      [event.target.name]: event.target.value
    });
  }
  async handleSubmit(evt){
    evt.preventDefault()
    // if this.state.caption is empty --> alert!
    if(this.state.caption == "") {
      alert('Caption cannot be empty! Please try again.')
    }
    else {
      let res = await axios.post('/generate',{caption: this.state.caption});
      if(res.status == 200) {
        document.getElementById("plan1").src = res.data[1]
      }
      else if (res.status == 500) {
        alert("There was an error. Please try again.")
      }
      // let res = await axios.get("/time");
      // console.log(res)
    }
  }
  render(){
    return (
      <div>
        <body>
        <section class="logoheader">
          <img id="logo" src={logo}></img>
        </section>

        <section class="form">
          <div>
            <textarea name="caption" rows="4" cols="50" placeholder="Please provide a description of the floor plan you would like to generate!" form="newplan" onChange={this.handleChange}></textarea>      
          </div>
          <form id="newplan" onSubmit={this.handleSubmit}>
            <input type="submit" />
          </form>
        </section>
        
        <section class="generatedplans">
          <div>
              <img id="plan1" src={mainphoto}></img>
            </div>
        </section>
        </body>
      </div>
    )
  }
  
}

export default App;
