'use strict'

const lambda_handler = async (event) => {
	console.log(event);
	const value = getRandomInt(100);
	const number = value % 2;
	
	return { number: number};
}

function getRandomInt(max) {
	return Math.floor(Math.random() * max)
}
    
module.exports = {
    lambda_handler,
}