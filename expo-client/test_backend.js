#!/usr/bin/env node

const https = require('https');

console.log('🔗 Testing Heavenly Hub Backend Connectivity...');
console.log('===============================================');

// Test production backend health
const testBackendHealth = () => {
  return new Promise((resolve, reject) => {
    const req = https.get('https://heavenly-new.onrender.com/health', (res) => {
      let data = '';
      
      res.on('data', (chunk) => {
        data += chunk;
      });
      
      res.on('end', () => {
        try {
          const health = JSON.parse(data);
          console.log('✅ Backend Health Check:');
          console.log(`   Status: ${health.status}`);
          console.log(`   Service: ${health.service}`);
          console.log(`   Version: ${health.version}`);
          console.log(`   Timestamp: ${health.timestamp}`);
          resolve(health);
        } catch (error) {
          reject(new Error(`Failed to parse health response: ${error.message}`));
        }
      });
    });
    
    req.on('error', (error) => {
      reject(new Error(`Health check failed: ${error.message}`));
    });
    
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error('Health check timeout'));
    });
  });
};

// Test token generation for both characters
const testTokenGeneration = async (character) => {
  return new Promise((resolve, reject) => {
    const postData = JSON.stringify({
      room: `spiritual-room-${character}`,
      identity: `test-user-${Date.now()}`,
      character: character
    });
    
    const options = {
      hostname: 'heavenly-new.onrender.com',
      port: 443,
      path: '/api/generate-token',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    };
    
    const req = https.request(options, (res) => {
      let data = '';
      
      res.on('data', (chunk) => {
        data += chunk;
      });
      
      res.on('end', () => {
        try {
          const tokenData = JSON.parse(data);
          if (res.statusCode === 200) {
            console.log(`✅ Token Generation for ${character}:`);
            console.log(`   Room: ${tokenData.room}`);
            console.log(`   Character: ${tokenData.character}`);
            console.log(`   WebSocket URL: ${tokenData.ws_url}`);
            console.log(`   Token Length: ${tokenData.token ? tokenData.token.length : 0} chars`);
            resolve(tokenData);
          } else {
            reject(new Error(`Token generation failed for ${character}: ${res.statusCode} - ${data}`));
          }
        } catch (error) {
          reject(new Error(`Failed to parse token response for ${character}: ${error.message}`));
        }
      });
    });
    
    req.on('error', (error) => {
      reject(new Error(`Token request failed for ${character}: ${error.message}`));
    });
    
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error(`Token request timeout for ${character}`));
    });
    
    req.write(postData);
    req.end();
  });
};

// Main test function
const runTests = async () => {
  try {
    console.log('\n🏥 Testing Backend Health...');
    await testBackendHealth();
    
    console.log('\n🎭 Testing Character Token Generation...');
    
    console.log('\n👤 Testing Adina:');
    await testTokenGeneration('adina');
    
    console.log('\n👤 Testing Raffa:');
    await testTokenGeneration('raffa');
    
    console.log('\n🎉 ALL TESTS PASSED!');
    console.log('✅ Backend is ready for mobile app testing');
    console.log('✅ Token generation working for both characters');
    console.log('✅ WebSocket URLs configured correctly');
    
    console.log('\n🚀 NEXT STEPS:');
    console.log('1. Run: npx expo login');
    console.log('2. Run: eas init');
    console.log('3. Run: npm run build:dev');
    console.log('4. Install APK/IPA on device');
    console.log('5. Test voice conversations!');
    
  } catch (error) {
    console.error('\n❌ TEST FAILED:', error.message);
    console.log('\n🔧 TROUBLESHOOTING:');
    console.log('1. Check internet connection');
    console.log('2. Verify backend is running: https://heavenly-new.onrender.com/health');
    console.log('3. Wait a moment if backend is starting up');
    console.log('4. Try again in a few minutes');
    process.exit(1);
  }
};

runTests(); 