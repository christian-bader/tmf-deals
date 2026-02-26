/**
 * Configuration helper for script properties.
 * 
 * Set these in Apps Script:
 * File > Project Settings > Script Properties
 * 
 * Required properties:
 * - SUPABASE_URL: https://xxx.supabase.co
 * - SUPABASE_KEY: your-anon-key
 * - ANTHROPIC_API_KEY: sk-ant-...
 */

function getConfig() {
  const props = PropertiesService.getScriptProperties();
  return {
    SUPABASE_URL: props.getProperty('SUPABASE_URL'),
    SUPABASE_KEY: props.getProperty('SUPABASE_KEY'),
    ANTHROPIC_API_KEY: props.getProperty('ANTHROPIC_API_KEY'),
  };
}

function validateConfig() {
  const config = getConfig();
  const missing = [];
  
  if (!config.SUPABASE_URL) missing.push('SUPABASE_URL');
  if (!config.SUPABASE_KEY) missing.push('SUPABASE_KEY');
  if (!config.ANTHROPIC_API_KEY) missing.push('ANTHROPIC_API_KEY');
  
  if (missing.length > 0) {
    throw new Error(
      'Missing script properties: ' + missing.join(', ') + '\n\n' +
      'Set them in: File > Project Settings > Script Properties'
    );
  }
  
  return config;
}

/**
 * Test configuration - run this first!
 */
function testConfig() {
  try {
    const config = validateConfig();
    console.log('✓ Configuration valid');
    console.log('  Supabase URL:', config.SUPABASE_URL);
    console.log('  Supabase Key:', config.SUPABASE_KEY.substring(0, 20) + '...');
    console.log('  Anthropic Key:', config.ANTHROPIC_API_KEY.substring(0, 15) + '...');
  } catch (e) {
    console.error('✗ Configuration error:', e.message);
  }
}
