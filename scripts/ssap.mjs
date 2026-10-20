#!/usr/bin/env node
// Private paired SSAP operations. Never publish the key or raw inventory output.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import https from 'node:https';
import http from 'node:http';
import WebSocket from 'ws';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const argv = process.argv.slice(2);
const ci = argv.indexOf('--config');
const configPath = ci >= 0 ? argv.splice(ci, 2)[1] : '.local/config.json';
const [action, ...args] = argv;
if (!['pair', 'inventory', 'capture', 'button', 'launch'].includes(action)) {
  console.error('Usage: node scripts/ssap.mjs --config .local/config.json pair|inventory|capture [name.jpg]|button NAME...|launch APP_ID');
  process.exit(1);
}
const config = JSON.parse(fs.readFileSync(path.resolve(root, configPath)));
const ssap = config.ssap;
const endpoint = new URL(ssap.url);
if (endpoint.protocol !== 'wss:' || endpoint.username || endpoint.password) throw Error('Use a wss:// URL without credentials');
const pin = (ssap.certificate_sha256 || '').replaceAll(':', '').toLowerCase();
if (!/^[a-f0-9]{64}$/.test(pin)) throw Error('Configure the SHA-256 TLS certificate fingerprint verified on your TV first');
const keyFile = path.resolve(root, ssap.client_key_file.replace(/^~(?=\/)/, os.homedir()));
const local = path.resolve(root, '.local');
const secrets = path.join(os.homedir(), '.secrets');
if (path.dirname(keyFile) !== secrets || !keyFile.endsWith('.env')) throw Error('Keep the SSAP key in ~/.secrets/*.env');
fs.mkdirSync(local, {recursive: true, mode: 0o700});

function verifyCertificate(socket) {
  const cert = socket.getPeerCertificate();
  if (!cert.raw || crypto.createHash('sha256').update(cert.raw).digest('hex') !== pin) {
    socket.destroy();
    throw Error('The TV certificate differs from the configured fingerprint');
  }
}
function connect(url, pinCertificate = true) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url, {rejectUnauthorized: false, perMessageDeflate: false,
      maxPayload: 16 * 1024 * 1024, handshakeTimeout: 10000});
    ws.on('error', reject);
    ws.once('open', () => {
      try { if (pinCertificate) verifyCertificate(ws._socket); resolve(ws); }
      catch (e) { ws.terminate(); reject(e); }
    });
  });
}
function receive(ws, id, accepted, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => done(Error('TV response timed out')), timeout);
    const closed = () => done(Error('TV connection closed'));
    const message = (bytes) => {
      let value;
      try { value = JSON.parse(bytes); } catch { return done(Error('Invalid TV response')); }
      if (value.id !== id) return;
      if (value.type === 'error') {
        const code = /^([0-9]{3})\b/.exec(String(value.error || ''));
        return done(Error('The TV rejected this operation' + (code ? ' (code ' + code[1] + ')' : '')));
      }
      if (accepted && !accepted(value)) return;
      done(null, value);
    };
    function done(error, value) {
      clearTimeout(timer);
      ws.off('message', message);
      ws.off('close', closed);
      error ? reject(error) : resolve(value);
    }
    ws.on('message', message);
    ws.once('close', closed);
  });
}
let serial = 0;
async function request(ws, uri, payload = {}) {
  const id = 'request-' + ++serial;
  const result = receive(ws, id);
  ws.send(JSON.stringify({id, type: 'request', uri: 'ssap://' + uri, payload}));
  const value = (await result).payload;
  if (!value || value.returnValue === false) throw Error('TV operation failed');
  return value;
}
function privateSave(file, bytes) {
  const fd = fs.openSync(file, 'w', 0o600);
  try { fs.fchmodSync(fd, 0o600); fs.writeFileSync(fd, bytes); } finally { fs.closeSync(fd); }
}
async function fetchCapture(url) {
  const image = new URL(url);
  if (image.hostname !== endpoint.hostname || !['http:', 'https:'].includes(image.protocol) || image.username || image.password) {
    throw Error('Capture URL does not belong to the configured TV');
  }
  return new Promise((resolve, reject) => {
    // SSAP serves ephemeral image URLs over HTTP on the tested firmware.
    const transport = image.protocol === 'https:' ? https : http;
    const req = transport.get(image, {rejectUnauthorized: false, timeout: 10000}, res => {
      if (res.statusCode !== 200) { res.resume(); return reject(Error('Capture download failed')); }
      if (image.protocol === 'https:') {
        try { verifyCertificate(res.socket); } catch (e) { res.destroy(); return reject(e); }
      }
      const chunks = [];
      let length = 0;
      res.on('data', bytes => {
        length += bytes.length;
        if (length > 16 * 1024 * 1024) res.destroy(Error('Capture exceeds size limit'));
        else chunks.push(bytes);
      });
      res.on('end', () => resolve(Buffer.concat(chunks)));
      res.on('error', reject);
    });
    req.on('timeout', () => req.destroy(Error('Capture timed out')));
    req.on('error', reject);
  });
}
let ws;
try {
  ws = await connect(endpoint);
  const hasKey = fs.existsSync(keyFile);
  if (action !== 'pair' && !hasKey) throw Error('Run pair and accept the TV prompt first');
  if (hasKey && (fs.statSync(keyFile).mode & 0o077)) throw Error('SSAP client key must have mode 600');
  const registration = receive(ws, 'register', value => value.type === 'registered', action === 'pair' ? 120000 : 10000);
  ws.send(JSON.stringify({id: 'register', type: 'register', payload: {
    pairingType: 'PROMPT', forcePairing: false,
    ...(hasKey ? {'client-key': JSON.parse(fs.readFileSync(keyFile, 'utf8').split(/\r?\n/).find(line => line.startsWith('WEBOS_CLIENT_KEY=')).slice('WEBOS_CLIENT_KEY='.length))} : {}),
    manifest: {manifestVersion: 1, appVersion: '0.1.0', permissions: [
      'CONTROL_TV_SCREEN', 'CONTROL_DISPLAY', 'CONTROL_MOUSE_AND_KEYBOARD', 'READ_INSTALLED_APPS',
      'READ_UPDATE_INFO', 'READ_APP_STATUS', 'LAUNCH', 'TEST_PROTECTED', 'TEST_SECURE'
    ]}
  }}));
  const paired = await registration;
  if (action === 'pair') {
    const key = paired.payload?.['client-key'];
    if (!key || typeof key !== 'string' || key.length > 512 || /\s/.test(key)) throw Error('Invalid pairing response');
    fs.mkdirSync(path.dirname(keyFile), {recursive: true, mode: 0o700});
    privateSave(keyFile, 'WEBOS_CLIENT_KEY=' + JSON.stringify(key) + '\n');
    console.log('Paired. Saved the private client key under ~/.secrets/.');
  } else if (action === 'inventory') {
    const result = {};
    for (const [name, uri] of [
      ['system', 'system/getSystemInfo'],
      ['software', 'com.webos.service.update/getCurrentSWInformation'],
      ['apps', 'com.webos.applicationManager/listApps']
    ]) {
      try { result[name] = await request(ws, uri); }
      catch (error) { result[name] = {unavailable:true, reason:error.message}; }
    }
    privateSave(path.join(local, 'inventory.json'), JSON.stringify(result, null, 2) + '\n');
    const unavailable = Object.entries(result).filter(([, value]) => value.unavailable).map(([name]) => name);
    console.log('Saved private inventory to .local/inventory.json.' +
      (unavailable.length ? ' Unavailable APIs: ' + unavailable.join(', ') + '.' : ''));
  } else if (action === 'capture') {
    const name = args[0] || 'screen.jpg';
    if (!/^[a-zA-Z0-9_.-]+\.jpg$/.test(name)) throw Error('Use a plain .jpg filename');
    const result = await request(ws, 'tv/executeOneShot', {method: 'DISPLAY', format: 'JPG', width: 1280, height: 720});
    const bytes = await fetchCapture(result.imageUri);
    if (bytes[0] !== 0xff || bytes[1] !== 0xd8) throw Error('Capture is not a JPEG');
    privateSave(path.join(local, name), bytes);
    console.log('Saved private capture to .local/' + name);
  } else if (action === 'button') {
    const allowed = new Set(['HOME', 'BACK', 'ENTER', 'LEFT', 'RIGHT', 'UP', 'DOWN', 'PLAY', 'PAUSE']);
    if (!args.length || args.some(name => !allowed.has(name))) throw Error('Unknown remote button');
    const result = await request(ws, 'com.webos.service.networkinput/getPointerInputSocket');
    const pointerUrl = new URL(result.socketPath);
    if (!['ws:', 'wss:'].includes(pointerUrl.protocol) || pointerUrl.hostname !== endpoint.hostname || pointerUrl.username || pointerUrl.password) throw Error('Pointer socket must belong to the configured TV');
    // Some firmware returns ws://. Only allowlisted button events use this socket.
    // The paired client key is sent only over the pinned SSAP wss connection.
    const pointer = await connect(pointerUrl, pointerUrl.protocol === 'wss:');
    try {
      for (const name of args) {
        pointer.send('type:button\nname:' + name + '\n\n');
        await new Promise(resolve => setTimeout(resolve, 350));
      }
    } finally { pointer.close(); }
    console.log('Sent ' + args.length + ' button events.');
  } else if (action === 'launch') {
    if (!args[0] || !/^[a-zA-Z0-9._-]{1,160}$/.test(args[0])) throw Error('Provide an app ID from the inventory');
    await request(ws, 'system.launcher/launch', {id: args[0], params: {}});
    console.log('TV acknowledged the launch request.');
  }
} catch (error) {
  console.error('Stopped: ' + error.message);
  process.exitCode = 1;
} finally {
  ws?.close();
  const closeTimer = setTimeout(() => ws?.terminate(), 1000);
  closeTimer.unref();
}
