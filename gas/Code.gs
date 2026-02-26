/**
 * TMF Deals - Email Outreach Automation
 * 
 * Main entry points for generating and sending outreach emails.
 * 
 * Workflow:
 * 1. Run generateSuggestedEmails() to create draft suggestions in Supabase
 * 2. Review suggestions in Supabase/React app, set status = 'approved'
 * 3. Run createDraftsFromApproved() to create Gmail drafts
 * 4. Review drafts in Gmail and send manually (or use sendApprovedDrafts())
 */

/**
 * Add menu to Google Sheets (if using as bound script).
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('TMF Outreach')
    .addItem('Generate Suggested Emails', 'generateSuggestedEmails')
    .addItem('Create Drafts from Approved', 'createDraftsFromApproved')
    .addSeparator()
    .addItem('Test Configuration', 'testConfig')
    .addItem('Test Supabase', 'testSupabase')
    .addItem('Test Anthropic', 'testAnthropic')
    .addToUi();
}

/**
 * STEP 1: Generate suggested emails for all opportunities.
 * Creates rows in suggested_emails table with status = 'draft'.
 */
function generateSuggestedEmails(limit = 20) {
  console.log('Fetching outreach opportunities...');
  const opportunities = fetchOpportunities(limit);
  console.log(`Found ${opportunities.length} opportunities`);
  
  let created = 0;
  let skipped = 0;
  let errors = 0;
  
  for (const opp of opportunities) {
    try {
      // Skip if no email
      if (!opp.email) {
        console.log(`Skipping ${opp.name}: no email`);
        insertSuppressionLog({
          broker_id: opp.broker_id,
          reason: 'no_email',
        });
        skipped++;
        continue;
      }
      
      // Skip if no listings
      const listings = opp.listings || [];
      if (listings.length === 0) {
        console.log(`Skipping ${opp.name}: no listings`);
        insertSuppressionLog({
          broker_id: opp.broker_id,
          reason: 'no_new_listings',
          new_listing_count: 0,
        });
        skipped++;
        continue;
      }
      
      // Classify template type
      const templateType = classifyTemplate(listings);
      const template = getTemplate(templateType);
      
      console.log(`Processing ${opp.name} (${opp.email}) - ${templateType}`);
      
      // Generate personalized opener with Claude
      const opener = personalizeEmail(opp, templateType);
      if (!opener) {
        console.log(`  Could not generate opener, skipping`);
        skipped++;
        continue;
      }
      
      // Build full email
      const firstName = getFirstName(opp.name);
      const subject = generateSubject(opp, templateType);
      const body = `Hi ${firstName},\n\n${opener}\n\n${template.body}`;
      
      // Get listing IDs
      const listingIds = listings.map(l => l.listing_id).filter(Boolean);
      
      // Insert suggested email
      insertSuggestedEmail({
        broker_id: opp.broker_id,
        new_listing_ids: listingIds,
        subject: subject,
        body_content: body,
        is_first_contact: !opp.last_contacted_at,
        status: 'draft',
      });
      
      console.log(`  ✓ Created suggested email: ${subject}`);
      created++;
      
      // Rate limit to avoid API throttling
      Utilities.sleep(500);
      
    } catch (e) {
      console.error(`  ✗ Error processing ${opp.name}: ${e.message}`);
      errors++;
    }
  }
  
  console.log('\n=== SUMMARY ===');
  console.log(`Created: ${created}`);
  console.log(`Skipped: ${skipped}`);
  console.log(`Errors: ${errors}`);
  
  return { created, skipped, errors };
}

/**
 * STEP 2: Create Gmail drafts from approved suggestions.
 * Reads suggested_emails with status = 'approved', creates drafts, logs to sent_email_logs.
 */
function createDraftsFromApproved(limit = 20) {
  console.log('Fetching approved suggestions...');
  const approved = fetchSuggestedEmails('approved', limit);
  console.log(`Found ${approved.length} approved emails`);
  
  let created = 0;
  let errors = 0;
  
  for (const email of approved) {
    try {
      // Get broker info
      const broker = fetchBroker(email.broker_id);
      if (!broker || !broker.email) {
        console.log(`Skipping email ${email.id}: broker not found or no email`);
        continue;
      }
      
      console.log(`Creating draft for ${broker.name} (${broker.email})`);
      
      // Create Gmail draft
      const draft = createEmailDraft(
        broker.email,
        email.subject,
        email.body_content
      );
      
      // Update suggested email status
      updateSuggestedEmail(email.id, { status: 'sent' });
      
      // Log to sent_email_logs
      insertSentEmailLog({
        suggested_email_id: email.id,
        broker_id: email.broker_id,
        gmail_message_id: draft.messageId,
        gmail_thread_id: draft.threadId,
        body_snapshot: email.body_content,
        listing_ids_included: email.new_listing_ids,
        send_status: 'sent',
      });
      
      console.log(`  ✓ Draft created: ${draft.draftId}`);
      created++;
      
    } catch (e) {
      console.error(`  ✗ Error creating draft: ${e.message}`);
      errors++;
    }
  }
  
  console.log('\n=== SUMMARY ===');
  console.log(`Drafts created: ${created}`);
  console.log(`Errors: ${errors}`);
  
  return { created, errors };
}

/**
 * Utility: Preview what would be generated for a single opportunity.
 */
function previewEmail(brokerId) {
  const broker = fetchBroker(brokerId);
  if (!broker) {
    console.log('Broker not found');
    return;
  }
  
  // Get their listings
  const opportunities = fetchOpportunities(100);
  const opp = opportunities.find(o => o.broker_id === brokerId);
  
  if (!opp) {
    console.log('No opportunity found for this broker');
    return;
  }
  
  const templateType = classifyTemplate(opp.listings);
  const template = getTemplate(templateType);
  const opener = personalizeEmail(opp, templateType);
  const subject = generateSubject(opp, templateType);
  const firstName = getFirstName(opp.name);
  
  console.log('=== PREVIEW ===');
  console.log('To:', broker.email);
  console.log('Subject:', subject);
  console.log('Template:', templateType);
  console.log('\n--- BODY ---');
  console.log(`Hi ${firstName},\n\n${opener}\n\n${template.body}`);
}

/**
 * Utility: Check for replies to sent emails.
 */
function checkForReplies() {
  console.log('This feature is not yet implemented.');
  console.log('To check replies, query sent_email_logs for gmail_thread_id');
  console.log('and use Gmail API to check thread message count.');
}
