'use strict'

const lambda_handler = async (event) => {
	console.log(event);
	
	return event.input.lambda1;
}
    
module.exports = {
    lambda_handler,
}