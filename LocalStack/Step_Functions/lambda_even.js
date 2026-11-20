'use strict'

const lambda_handler = async (event) => {
	console.log(event);
	
	return "The number is even";
}
    
module.exports = {
    lambda_handler,
}