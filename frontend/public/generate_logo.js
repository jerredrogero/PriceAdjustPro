const { createCanvas } = require('canvas');
const fs = require('fs');

// Create canvas
const canvas = createCanvas(192, 192);
const ctx = canvas.getContext('2d');

// Set background
ctx.fillStyle = '#005DAA'; // Costco blue
ctx.fillRect(0, 0, 192, 192);

// Draw shopping cart icon
ctx.strokeStyle = '#FFFFFF';
ctx.lineWidth = 8;
ctx.beginPath();

// Cart base
ctx.moveTo(40, 140);
ctx.lineTo(152, 140);

// Cart body
ctx.moveTo(50, 70);
ctx.lineTo(142, 70);
ctx.lineTo(132, 120);
ctx.lineTo(60, 120);
ctx.closePath();

// Cart wheels
ctx.moveTo(70, 140);
ctx.arc(70, 150, 10, 0, Math.PI * 2);
ctx.moveTo(122, 140);
ctx.arc(122, 150, 10, 0, Math.PI * 2);

// Handle
ctx.moveTo(132, 70);
ctx.lineTo(152, 40);

ctx.stroke();

// Add price tag
ctx.fillStyle = '#FFFFFF';
ctx.font = 'bold 48px Arial';
ctx.textAlign = 'center';
ctx.fillText('$', 96, 105);

// Save to file
const buffer = canvas.toBuffer('image/png');
fs.writeFileSync('logo192.png', buffer); 