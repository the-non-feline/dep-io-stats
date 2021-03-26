const { s } = require('./creator_center_animals'); 
const fs = require('fs'); 

const FILENAME = 'animals.json'; 

json = JSON.stringify(s); 

fs.writeFile(FILENAME, json, function(err) {
    console.log(err); 
}); 