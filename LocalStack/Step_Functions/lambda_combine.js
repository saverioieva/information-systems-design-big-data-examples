'use strict'

const lambda_handler = async (event) => {
	console.log(event);
	
	return `Together lambda_1 and lambda_2 say ${event.input}`;
}
    
module.exports = {
    lambda_handler,
}