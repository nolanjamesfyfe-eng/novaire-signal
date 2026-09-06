'use strict';
const crypto=require('node:crypto');
const MAX_PNG_BYTES=5*1024*1024;
function fail(message){const error=new Error(message);error.statusCode=400;throw error;}
let crcTable;
function crc32(buffer){
  if(!crcTable)crcTable=Array.from({length:256},(_,n)=>{let c=n;for(let k=0;k<8;k++)c=(c>>>1)^((c&1)?0xedb88320:0);return c>>>0;});
  let c=0xffffffff;for(const byte of buffer)c=crcTable[(c^byte)&255]^(c>>>8);return(c^0xffffffff)>>>0;
}
function parsePngDataUrl(value){
  if(typeof value!=='string'||!value.startsWith('data:image/png;base64,'))fail('A PNG image is required.');
  const encoded=value.slice(22);if(!encoded||encoded.length>Math.ceil(MAX_PNG_BYTES/3)*4+4||!/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)||encoded.length%4!==0)fail('Invalid PNG base64 data.');
  const png=Buffer.from(encoded,'base64');if(png.length>MAX_PNG_BYTES)fail('PNG exceeds the 5 MB limit.');
  if(png.length<45||!png.subarray(0,8).equals(Buffer.from('89504e470d0a1a0a','hex')))fail('Invalid PNG file.');
  let offset=8,first=true,sawIdat=false,sawEnd=false;
  while(offset+12<=png.length){
    const length=png.readUInt32BE(offset);if(length>MAX_PNG_BYTES||offset+12+length>png.length)fail('Invalid PNG structure.');
    const type=png.toString('ascii',offset+4,offset+8),dataStart=offset+8,end=dataStart+length;
    const expected=png.readUInt32BE(end),actual=crc32(png.subarray(offset+4,end));if(expected!==actual)fail('Invalid PNG checksum.');
    if(first){if(type!=='IHDR'||length!==13)fail('Invalid PNG header.');const w=png.readUInt32BE(dataStart),h=png.readUInt32BE(dataStart+4);if(!w||!h||w>8192||h>8192)fail('Invalid PNG dimensions.');first=false;}
    if(type==='IDAT')sawIdat=true;
    if(type==='IEND'){if(length!==0||!sawIdat||end+4!==png.length)fail('Invalid PNG ending.');sawEnd=true;break;}
    offset=end+4;
  }
  if(!sawEnd)fail('Invalid PNG file.');return png;
}
function weightedLength(text){let total=0;for(const char of text){const cp=char.codePointAt(0);total+=cp<=0x10ff||cp>=0x2000&&cp<=0x200d||cp>=0x2010&&cp<=0x201f||cp>=0x2032&&cp<=0x2037?1:2;}return total;}
function validatePostInput(data){
  if(!data||typeof data!=='object'||Array.isArray(data))fail('Invalid request.');
  if(data.confirmation!==true)fail('Explicit confirmation is required.');
  if(typeof data.requestId!=='string'||!crypto.randomUUID||!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(data.requestId))fail('A valid requestId is required.');
  // Newlines are part of the quote-card format; reject all other C0/C1 controls.
  if(typeof data.text!=='string'||!data.text.trim()||data.text!==data.text.trim()||/[\u0000-\u0009\u000b-\u001f\u007f-\u009f]/u.test(data.text))fail('Post text is invalid.');
  if(/(?:https?:\/\/|www\.|\b[a-z0-9-]+\.(?:com|net|org|io|co|ai|app|dev|xyz|me|ca|uk|th)(?:\/|\b))/iu.test(data.text))fail('URLs are not allowed.');
  if(/novaire\s*signal|novairesignal/iu.test(data.text))fail('Novaire Signal source markers are not allowed.');
  if(weightedLength(data.text)>280)fail('Post text exceeds the conservative 280 weighted-character limit.');
  return{text:data.text,png:parsePngDataUrl(data.imageDataUrl),requestId:data.requestId};
}
module.exports={MAX_PNG_BYTES,parsePngDataUrl,weightedLength,validatePostInput};
