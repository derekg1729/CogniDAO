#!/usr/bin/env node

/**
 * Fetch Schema Script
 * 
 * This script fetches JSON schema files from the backend repo, generates TypeScript types,
 * and then removes the JSON schema files (keeping only the TypeScript definitions).
 * 
 * It can be used in two ways:
 * 
 * 1. Local mode: Copy schemas from local backend repo path
 *    node fetch-schemas.js --local /path/to/backend/schemas/backend
 * 
 * 2. Remote mode: Fetch schemas from a remote URL (e.g., GitHub raw content)
 *    node fetch-schemas.js --remote https://raw.githubusercontent.com/username/repo/main/schemas/backend
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const { spawnSync } = require('child_process');

// Configuration
// These will be populated dynamically
let schemas = [];
const outputDir = path.join(process.cwd(), 'schemas');

// Create output directory if it doesn't exist
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

// Parse command line arguments
const args = process.argv.slice(2);
const mode = args[0];
const source = args[1];

if (!mode || !source) {
  console.error('Usage:');
  console.error('  node fetch-schemas.js --local /path/to/backend/schemas/backend');
  console.error('  node fetch-schemas.js --remote https://raw.githubusercontent.com/username/repo/main/schemas/backend');
  process.exit(1);
}

// Function to discover schemas in a directory
function discoverSchemas(directory) {
  console.log(`🔍 Discovering schemas in: ${directory}`);
  
  try {
    const files = fs.readdirSync(directory);
    const schemaFiles = files.filter(file => file.endsWith('.schema.json'));
    
    if (schemaFiles.length === 0) {
      console.error('❌ No schema files found!');
      process.exit(1);
    }
    
    console.log(`✅ Found ${schemaFiles.length} schema files`);
    return schemaFiles;
  } catch (error) {
    console.error(`❌ Error discovering schemas: ${error.message}`);
    process.exit(1);
  }
}

// Function to copy local schema files
function copyLocalSchemas(sourceDir) {
  console.log(`📂 Copying schemas from local path: ${sourceDir}`);
  
  schemas = discoverSchemas(sourceDir);
  
  schemas.forEach(schema => {
    const sourcePath = path.join(sourceDir, schema);
    const destPath = path.join(outputDir, schema);
    
    if (!fs.existsSync(sourcePath)) {
      console.error(`❌ Error: Schema file not found: ${sourcePath}`);
      return;
    }
    
    fs.copyFileSync(sourcePath, destPath);
    console.log(`✅ Copied: ${schema}`);
  });
}

// Function to download remote schema files
async function downloadRemoteSchemas(baseUrl) {
  console.log(`🌐 Connecting to remote URL: ${baseUrl}`);
  
  // First, try to get a listing of schemas
  try {
    // Make a direct HTTP request to try to discover schemas
    // This is a simple implementation - in production, you might want to use
    // a more robust way to discover schemas like an index.json file
    
    // For this example, we'll try a few common schema names
    const commonSchemas = [
      'chatmessage.schema.json',
      'chatresponse.schema.json',
      'completequeryrequest.schema.json',
      'errorresponse.schema.json'
    ];
    
    // Test if we can access these schemas
    const testPromises = commonSchemas.map(schema => {
      return new Promise(resolve => {
        const url = `${baseUrl}/${schema}`;
        https.get(url, (response) => {
          if (response.statusCode === 200) {
            resolve(schema);
          } else {
            resolve(null);
          }
        }).on('error', () => resolve(null));
      });
    });
    
    const availableSchemas = (await Promise.all(testPromises)).filter(Boolean);
    
    if (availableSchemas.length === 0) {
      console.error('❌ No schemas could be found at the remote URL');
      console.error('Please make sure the URL points to a directory with .schema.json files');
      process.exit(1);
    }
    
    schemas = availableSchemas;
    console.log(`✅ Found ${schemas.length} schemas at remote URL`);
  } catch (error) {
    console.error(`❌ Error discovering remote schemas: ${error.message}`);
    process.exit(1);
  }
  
  console.log(`🌐 Downloading schemas from remote URL: ${baseUrl}`);
  
  const downloadPromises = schemas.map(schema => {
    return new Promise((resolve, reject) => {
      const url = `${baseUrl}/${schema}`;
      const destPath = path.join(outputDir, schema);
      
      https.get(url, (response) => {
        if (response.statusCode !== 200) {
          reject(new Error(`Failed to download ${url}: ${response.statusCode}`));
          return;
        }
        
        const file = fs.createWriteStream(destPath);
        response.pipe(file);
        
        file.on('finish', () => {
          file.close();
          console.log(`✅ Downloaded: ${schema}`);
          resolve();
        });
      }).on('error', (error) => {
        fs.unlink(destPath, () => {}); // Delete the file if there was an error
        reject(error);
      });
    });
  });
  
  return Promise.all(downloadPromises);
}

// Function to generate TypeScript types from JSON schemas
function generateTypeScriptTypes() {
  console.log('🔄 Generating TypeScript types...');
  
  schemas.forEach(schema => {
    const schemaPath = path.join(outputDir, schema);
    const typeName = schema.replace('.schema.json', '.d.ts');
    const typePath = path.join(outputDir, typeName);
    
    // Run json-schema-to-typescript
    const result = spawnSync('npx', [
      'json-schema-to-typescript',
      schemaPath,
      '--out',
      typePath
    ], { stdio: 'inherit' });
    
    if (result.error) {
      console.error(`❌ Error generating types for ${schema}: ${result.error.message}`);
    } else {
      console.log(`✅ Generated types: ${typeName}`);
    }
  });
}

// Function to clean up JSON schema files
function cleanupSchemaFiles() {
  console.log('🧹 Removing JSON schema files (keeping only TypeScript types)...');
  
  schemas.forEach(schema => {
    const schemaPath = path.join(outputDir, schema);
    fs.unlinkSync(schemaPath);
    console.log(`✅ Removed: ${schema}`);
  });
}

// Main execution
async function main() {
  try {
    // Step 1: Get schema files
    if (mode === '--local') {
      copyLocalSchemas(source);
    } else if (mode === '--remote') {
      await downloadRemoteSchemas(source);
    } else {
      console.error('Invalid mode. Use --local or --remote');
      process.exit(1);
    }
    
    // Step 2: Generate TypeScript types
    generateTypeScriptTypes();
    
    // Step 3: Clean up JSON schema files
    cleanupSchemaFiles();
    
    console.log('🎉 All done! TypeScript types have been generated and JSON schemas removed.');
  } catch (error) {
    console.error(`❌ Error: ${error.message}`);
    process.exit(1);
  }
}

main(); 