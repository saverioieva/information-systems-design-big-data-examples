'use strict'

const apiHandler = (event, context, callback) => {
	console.log(JSON.stringify(event));
	const body = JSON.parse(event.body);	
	const name = body.name;
	const surname = body.surname;
    callback(null, {
        statusCode: 200,
        body: JSON.stringify({
            message: `Hello ${name} ${surname}`
        }),
    });
}
    
module.exports = {
    apiHandler,
}