# Office 365 MCP Server - User Guide

**Use Office 365 with Claude Desktop through natural language!**

## What is the MCP Server?

The Office 365 MCP (Model Context Protocol) Server allows you to interact with your Office 365 account directly from Claude Desktop using natural language. No need to remember commands or syntax - just ask Claude in plain English!

## Quick Start

### Prerequisites

- **Python 3.10+** installed
- **Claude Desktop** installed
- **Office 365 account** with appropriate permissions

### Installation

1. **Install the o365-cli package with MCP support:**

```bash
pip install git+https://github.com/shitchell/o365-cli.git
pip install "o365-cli[mcp]"  # Install MCP dependencies
```

2. **Configure Office 365 authentication:**

```bash
o365 auth login
```

Follow the prompts to authenticate with your Office 365 account.

3. **Configure Claude Desktop:**

Edit your Claude Desktop config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

Add this to your `mcpServers` section:

```json
{
  "mcpServers": {
    "office365": {
      "command": "/path/to/o365-mcp"
    }
  }
}
```

To find the correct path, run:
```bash
which o365-mcp  # macOS/Linux
where o365-mcp  # Windows
```

4. **Restart Claude Desktop**

Quit and reopen Claude Desktop completely.

5. **Verify it's working**

In Claude Desktop, you should see a hammer icon (🔨) in the bottom-right. Click it to see available MCP servers. You should see "office365" with 20 tools listed.

## What Can You Do?

The MCP server provides access to **20 tools** across 6 categories:

### 📧 Email (3 tools)
- Read and filter emails
- Get full email content with attachments
- Send emails

### 📅 Calendar (3 tools)
- List calendar events
- Create new events (including Teams meetings)
- Delete events

### 📁 Files (4 tools)
- List OneDrive files and folders
- Search for files
- Download files
- Upload files

### 💬 Teams Chat (4 tools)
- List Teams chats
- Read chat messages
- Send chat messages
- Search across chats

### 👥 Contacts (2 tools)
- Search for contacts
- List all contacts

### 🎥 Recordings (4 tools)
- List Teams meeting recordings
- Search recordings
- Download recordings
- Get meeting transcripts

## Example Queries

### Email Examples

**Check unread emails:**
```
What unread emails do I have from the last 2 days?
```

**Search emails:**
```
Show me emails from john@example.com about the project update
```

**Get email details:**
```
Get the full content of email ID AAMkAGI2...
```

**Send an email:**
```
Send an email to alice@example.com with subject "Meeting Follow-up"
and body "Thanks for attending today's meeting..."
```

### Calendar Examples

**Check today's schedule:**
```
What meetings do I have today?
```

**View upcoming week:**
```
Show me my calendar for the next 7 days
```

**Create a meeting:**
```
Create a Teams meeting titled "Project Sync" for tomorrow at 2pm
for 1 hour with john@example.com and alice@example.com
```

**Delete an event:**
```
Delete calendar event ID AAMkAGI2...
```

### Files Examples

**List files:**
```
What files are in my OneDrive Documents folder?
```

**Search for files:**
```
Search my OneDrive for "budget" Excel files
```

**Download a file:**
```
Download file ID 01BYE5RZ... to /tmp
```

**Upload a file:**
```
Upload /Users/me/report.pdf to /Documents/Reports/ in OneDrive
```

### Teams Chat Examples

**List chats:**
```
Show me my recent Teams chats
```

**Read messages:**
```
Read the last 10 messages from chat ID 19:abc123...
```

**Send a message:**
```
Send "Great work everyone!" to chat ID 19:abc123...
```

**Search messages:**
```
Search my Teams chats for "project deadline"
```

### Contacts Examples

**Search contacts:**
```
Find contact information for John Doe
```

**List all contacts:**
```
Show me all my Office 365 contacts
```

### Recordings Examples

**List recordings:**
```
Show me Teams meeting recordings from the last week
```

**Search recordings:**
```
Find recordings about "sprint planning"
```

**Get transcript:**
```
Get the transcript for recording ID 01BYE5RZ...
```

## Prompt Templates

The server includes 3 helpful prompt templates you can use:

### check_unread_emails
Quickly summarize your unread emails with:
- Count of unread emails
- Urgent/important messages
- Brief summary of topics

### todays_schedule
Get a formatted overview of today's meetings:
- What meetings you have
- Start/end times
- Attendees
- Conflicts or back-to-back meetings

### search_recent_chats
Search through recent Teams chats and get a summary of results.

## Tips for Best Results

### 1. **Be Specific with Dates**

✅ Good:
- "emails from the last 2 days"
- "calendar for tomorrow"
- "recordings since Monday"

❌ Less specific:
- "recent emails"
- "upcoming events"

### 2. **Use IDs for Precise Operations**

When Claude shows you an email, event, or file, it will include the ID. Use that ID for follow-up actions:

```
"Get the full content of email ID AAMkAGI2..."
"Delete calendar event ID AAMkAGI2..."
```

### 3. **Combine Multiple Requests**

Claude can perform multiple operations in one conversation:

```
"Check my unread emails, then show me today's calendar,
then list my recent Teams chats"
```

### 4. **Ask for Summaries**

Claude can analyze the data for you:

```
"Read my unread emails and summarize the most important ones"
"Look at my calendar for this week and tell me if I'm overbooked"
```

## Troubleshooting

### Server Not Appearing in Claude Desktop

1. **Check the config file syntax**
   - Must be valid JSON
   - Check for missing commas or quotes

2. **Verify the command path**
   ```bash
   which o365-mcp  # Should return a valid path
   o365-mcp        # Should start the server (press Ctrl+C to stop)
   ```

3. **Check Claude Desktop logs**
   - macOS: `~/Library/Logs/Claude/`
   - Look for errors related to "office365"

4. **Restart Claude Desktop completely**
   - Quit fully (Cmd+Q on Mac)
   - Reopen

### Authentication Errors

If you see "Not authenticated" errors:

```bash
# Check authentication status
o365 auth status

# Re-authenticate if needed
o365 auth login

# Refresh token
o365 auth refresh
```

### Tools Not Working

1. **Verify permissions**
   - Check your Office 365 account has the necessary permissions
   - Some features require specific licenses (e.g., Teams for chat/recordings)

2. **Test with CLI**
   - Try the equivalent CLI command first
   - Example: `o365 mail read --unread`

3. **Check error messages**
   - Claude will show error details
   - Common issues: invalid date formats, missing IDs, permission errors

### Performance Issues

- **Limit result counts**: Use smaller limits for faster responses
  - "Show me my last 5 emails" instead of "Show me all emails"
- **Be specific with dates**: Narrower date ranges return faster
- **Use search instead of list**: Searching is more efficient than listing all items

## Privacy & Security

- **Tokens stored locally**: Your Office 365 tokens are stored in `~/.o365/tokens.json` with restricted permissions (0600)
- **No data collection**: The MCP server doesn't send any data to third parties
- **Runs locally**: The server runs on your machine, not in the cloud
- **Uses OAuth2**: Industry-standard authentication protocol
- **Read-only by default**: Most operations are read-only; write operations require explicit confirmation

## Advanced Usage

### Custom Filters

You can use advanced filters with specific tools:

```
"Search emails in my Sent folder from last month"
"List calendar events for next Monday through Friday"
"Find Excel files in my OneDrive modified in the last week"
```

### Batch Operations

Claude can help with multiple operations:

```
"For each unread email from my boss, create a task in my calendar"
"Download all PDF files from my Documents folder"
```

### Data Analysis

Use Claude's analytical abilities:

```
"Analyze my calendar for this month and tell me how much time
I spend in meetings vs. focus time"

"Look at my recent Teams chats and identify recurring topics"
```

## Limitations

### Current Limitations

- **Personal OneDrive only**: Shared drives require admin consent
- **No real-time updates**: Data is fetched on-demand
- **Rate limits**: Microsoft Graph API has rate limits
- **Teams features**: Require Teams license

### Future Enhancements

See `docs/MCP_IMPLEMENTATION_PLAN.md` for planned features:
- Real-time notifications
- Batch operations
- Advanced search
- File content extraction
- Multi-account support

## Getting Help

### Resources

- **Documentation**: Check `docs/` folder for detailed guides
- **Examples**: See this guide's examples section
- **Issues**: Report bugs at the GitHub repository
- **CLI Help**: Run `o365 --help` for CLI documentation

### Common Questions

**Q: Can I use this with multiple Office 365 accounts?**
A: Currently, only one account at a time. You can switch with `o365 auth login`.

**Q: Does this work with personal Microsoft accounts?**
A: It's designed for Office 365/Microsoft 365 business accounts. Personal accounts may have limited functionality.

**Q: Is my data secure?**
A: Yes! All authentication happens locally, tokens are stored securely, and the server runs on your machine.

**Q: Can I use this without Claude Desktop?**
A: Yes! Any MCP-compatible client can use this server. You can also use the CLI directly: `o365 mail read --unread`

**Q: What permissions does this need?**
A: The minimum Office 365 permissions required are listed during authentication. You can review them in the auth flow.

## Next Steps

- **Try the prompt templates**: Click the bookmark icon in Claude Desktop
- **Explore the CLI**: Run `o365 --help` to see all CLI commands
- **Check the docs**: Read `MCP_IMPLEMENTATION_PLAN.md` for technical details
- **Share feedback**: Let us know what features you'd like to see!

---

**Happy prompting! 🚀**

Last updated: 2025-10-18
