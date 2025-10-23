#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Parse .env.local file
function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    console.error(`❌ ${filePath} not found`);
    return null;
  }

  const content = fs.readFileSync(filePath, 'utf8');
  const env = {};

  content.split('\n').forEach(line => {
    line = line.trim();
    if (line && !line.startsWith('#')) {
      const [key, ...valueParts] = line.split('=');
      if (key && valueParts.length) {
        env[key.trim()] = valueParts.join('=').trim();
      }
    }
  });

  return env;
}

console.log('🔐 Syncing auth config from .env.local...\n');

// Read .env.local (now in the llmops-agent-ui folder)
const envPath = path.join(__dirname, '../.env.local');
const env = parseEnvFile(envPath);

if (!env) {
  process.exit(1);
}

// Extract auth config
const authConfig = {
  DEMO_USERNAME: env.DEMO_USERNAME || 'demo',
  DEMO_PASSWORD: env.DEMO_PASSWORD || 'password'
};

console.log('✅ Parsed .env.local');
console.log(`   Username: ${authConfig.DEMO_USERNAME}`);
console.log(`   Password: ${'*'.repeat(authConfig.DEMO_PASSWORD.length)}\n`);

// Generate auth-config.js
const configContent = `// Auto-generated authentication config
// DO NOT commit this file to version control
window.AUTH_CONFIG = ${JSON.stringify(authConfig, null, 2)};
`;

const outputPath = path.join(__dirname, '../public/auth-config.js');
fs.writeFileSync(outputPath, configContent);

console.log(`✅ Generated auth config at: ${outputPath}\n`);
console.log('✨ Auth config sync complete!');
