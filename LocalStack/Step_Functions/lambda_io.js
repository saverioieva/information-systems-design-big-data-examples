'use strict'

const lambda_handler = async (event) => {
	console.log(event);
	
	return {
		status: "confirmed",
		trackingId: "78910"
	};
}
    
module.exports = {
    lambda_handler,
}