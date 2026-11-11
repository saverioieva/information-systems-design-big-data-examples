'use strict'
const AWS = require("aws-sdk");

// Set the region
AWS.config.update({ region: "us-east-1" });

// Create an SQS service object
const sqs = new AWS.SQS({ apiVersion: "2012-11-05" });

const lambda_handler = async (event) => {
	console.log(event);
	const body = JSON.parse(event.body);	
	const queueName = body.name;
	
	const params = {
		QueueName: queueName,
	};
	
	const data = await sqs.createQueue(params).promise();
	console.log(data);
	
	return {
      statusCode: 201,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ queueURL: data.QueueUrl }),
    };
}

    
module.exports = {
    lambda_handler,
}