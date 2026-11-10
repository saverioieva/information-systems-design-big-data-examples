'use strict'
const AWS = require('aws-sdk');
const s3 = new AWS.S3({apiVersion: '2006-03-01'});

const apiHandler = async (event) => {
	try {
		const body = JSON.parse(event.body);
		const params = {
			Bucket: 'test-s3-bucket',
			Key: `person-${body.name}-${body.surname}.txt`,
			Body: event.body
		};
	
		await s3.putObject(params).promise();
		
		return {
			statusCode: 200,
			body: JSON.stringify({ message: 'File uploaded successfully'})
		};
	} catch (error) {
		return {
			statusCode: 500,
			body: JSON.stringify({ message: error.message, name: error.name, stack: error.stack })
		};
	}
}
    
module.exports = {
    apiHandler,
}