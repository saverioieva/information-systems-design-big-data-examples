'use strict'

const apiHandler = (event, context, callback) => {
	console.log(JSON.stringify(event));
	const name = event.queryStringParameters.name;
	const surname = event.queryStringParameters.surname;
    callback(null, {
        statusCode: 200,
        body: JSON.stringify({
            message: `Hello from Lambda: ${name} ${surname}`
        }),
    }); 
}
    
module.exports = {
    apiHandler,
}