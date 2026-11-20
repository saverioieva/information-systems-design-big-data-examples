'use strict'

const lambda_handler = async (event) => {
	console.log(event);
	
	return event.input.lambda2;
}
    
module.exports = {
    lambda_handler,
}