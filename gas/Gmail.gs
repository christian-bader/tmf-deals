/**
 * Gmail integration for creating drafts and sending emails.
 */

/**
 * Create a Gmail draft.
 * Returns the draft object with ID and message info.
 */
function createEmailDraft(to, subject, body) {
  const draft = GmailApp.createDraft(to, subject, body);
  const message = draft.getMessage();
  
  return {
    draftId: draft.getId(),
    messageId: message.getId(),
    threadId: message.getThread().getId(),
  };
}

/**
 * Send an existing draft by ID.
 */
function sendDraft(draftId) {
  const drafts = GmailApp.getDrafts();
  const draft = drafts.find(d => d.getId() === draftId);
  
  if (!draft) {
    throw new Error(`Draft not found: ${draftId}`);
  }
  
  const message = draft.send();
  return {
    messageId: message.getId(),
    threadId: message.getThread().getId(),
  };
}

/**
 * Check if a thread has replies (messages > 1).
 */
function hasThreadReplies(threadId) {
  try {
    const thread = GmailApp.getThreadById(threadId);
    if (!thread) return false;
    return thread.getMessageCount() > 1;
  } catch (e) {
    console.error('Error checking thread:', e);
    return false;
  }
}

/**
 * Get all drafts in Gmail.
 */
function listDrafts(limit = 20) {
  const drafts = GmailApp.getDrafts().slice(0, limit);
  return drafts.map(d => {
    const msg = d.getMessage();
    return {
      draftId: d.getId(),
      to: msg.getTo(),
      subject: msg.getSubject(),
      date: msg.getDate(),
    };
  });
}
