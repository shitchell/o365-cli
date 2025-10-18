# o365-cli MCP Documentation

This directory contains comprehensive documentation for implementing Model Context Protocol (MCP) server capabilities in o365-cli.

## 📚 Documentation Files

### [MCP_IMPLEMENTATION_PLAN.md](MCP_IMPLEMENTATION_PLAN.md)
**Comprehensive implementation guide with detailed phases, tasks, and technical specifications.**

**What's inside:**
- Phase-by-phase breakdown (6 phases)
- Detailed technical requirements for each task
- Code examples and patterns
- Testing strategies
- Success criteria
- Timeline estimates (6-10 days)
- Risk mitigation strategies
- Future enhancement ideas

**Best for:** Understanding the full scope, planning the project, reference during implementation.

---

### [MCP_ARCHITECTURE.md](MCP_ARCHITECTURE.md)
**Technical architecture documentation with diagrams, data flows, and system design.**

**What's inside:**
- System architecture diagrams
- Component responsibilities
- Data schemas (email, calendar, files, etc.)
- Process flows (how requests work end-to-end)
- Authentication flow
- MCP protocol message formats
- Deployment architecture
- Error handling strategy
- Performance considerations
- Security considerations

**Best for:** Understanding how everything fits together, making architectural decisions, onboarding new developers.

---

### [MCP_IMPLEMENTATION_CHECKLIST.md](MCP_IMPLEMENTATION_CHECKLIST.md)
**Step-by-step checklist for executing the implementation.**

**What's inside:**
- 7 phases broken into individual checkboxes
- Over 100 discrete tasks to complete
- Clear validation steps for each task
- Quick start commands
- Success criteria
- Estimated timeline
- **TESTING checkpoints after EVERY change**

**Best for:** Day-to-day implementation work, tracking progress, ensuring nothing is missed.

---

### [MCP_TESTING_STRATEGY.md](MCP_TESTING_STRATEGY.md) ⚠️ **CRITICAL - READ FIRST**
**Comprehensive testing strategy to ensure ZERO regressions in CLI functionality.**

**What's inside:**
- Test baseline: 66 passing tests that MUST stay passing
- Before/after testing procedures for each refactoring
- Regression prevention checklist
- Test-driven development workflow
- Manual CLI testing checklist
- Troubleshooting guide
- Success metrics per phase

**Best for:** Understanding how to preserve existing CLI functionality while adding MCP features. READ THIS BEFORE STARTING IMPLEMENTATION!

---

## 🚀 Quick Start

### If you're just getting started:
1. Read **MCP_IMPLEMENTATION_PLAN.md** (sections 1-3) to understand what MCP is and why we're adding it
2. Review **MCP_ARCHITECTURE.md** to understand the system design
3. Use **MCP_IMPLEMENTATION_CHECKLIST.md** as your daily guide during implementation

### If you're implementing:
1. Open **MCP_IMPLEMENTATION_CHECKLIST.md** in your editor
2. Work through phases sequentially
3. Check off items as you complete them
4. Reference **MCP_IMPLEMENTATION_PLAN.md** for detailed instructions on each task
5. Reference **MCP_ARCHITECTURE.md** for architectural questions

### If you're reviewing code:
1. Check **MCP_ARCHITECTURE.md** for design patterns
2. Verify implementation matches the architecture
3. Use **MCP_IMPLEMENTATION_CHECKLIST.md** to ensure all tasks completed

---

## 🎯 Project Goals

Add Model Context Protocol (MCP) server to o365-cli to enable:

1. **Natural language interaction** with Office 365 via Claude and other LLM clients
2. **Programmatic access** to email, calendar, files, Teams chats, and more
3. **Integration with other tools** in the MCP ecosystem

**Example interactions:**
- "Show my unread emails from the last 2 days"
- "What meetings do I have tomorrow?"
- "Search OneDrive for the Q4 budget spreadsheet"
- "List my recent Teams chats"

---

## 📋 Implementation Overview

### Phase 1: Project Setup (2 hours)
- Update Python version to 3.10+
- Add MCP SDK dependency
- Add console script entry point

### Phase 2: Data Layer Refactoring (1-2 days)
- Separate data retrieval from formatting
- Create `*_structured()` functions for each module
- Maintain CLI backward compatibility

### Phase 3: MCP Server Implementation (2-3 days)
- Create `o365/mcp_server.py`
- Implement 15+ tools (mail, calendar, files, chat, etc.)
- Implement resources and prompts
- Add CLI command to start server

### Phase 4: Testing (1-2 days)
- Unit tests for all tools
- Integration tests
- Manual testing with Claude Desktop

### Phase 5: Documentation (1 day)
- User guide
- Developer guide
- API reference
- Update README

### Phase 6: Optimization & Polish (1 day)
- Performance optimization
- Error handling refinement
- Security review

**Total estimated time: 6-10 days**

---

## 🛠️ Technology Stack

- **MCP SDK:** Official Python SDK for Model Context Protocol
- **FastMCP:** High-level framework (included in MCP SDK)
- **Python:** 3.10+ (async/await support)
- **Microsoft Graph API:** Backend API for Office 365
- **OAuth2:** Device code flow for authentication

---

## 🏗️ Architecture Summary

```
Claude Desktop
      ↓
   MCP Client (stdio JSON-RPC)
      ↓
o365 MCP Server (o365/mcp_server.py)
      ↓
Refactored Modules (*_structured functions)
      ↓
Microsoft Graph API
```

**Key architectural decisions:**
1. **Wrapper approach** - MCP wraps existing CLI logic
2. **Structured data functions** - Separate data from formatting
3. **Shared authentication** - Reuse existing token management
4. **Stateless server** - Config/tokens stored on disk

---

## 📊 Tools to Implement

### Email (4 tools)
- `read_emails` - Read with filters
- `get_email_content` - Get full email
- `send_email` - Send new email
- `archive_emails` - Archive messages

### Calendar (3 tools)
- `list_calendar_events` - List events
- `create_calendar_event` - Create new event
- `delete_calendar_event` - Delete event

### Files (4 tools)
- `list_onedrive_files` - List files/folders
- `search_onedrive` - Search files
- `download_file` - Download file
- `upload_file` - Upload file

### Teams Chat (4 tools)
- `list_teams_chats` - List chats
- `read_chat_messages` - Read messages
- `send_chat_message` - Send message
- `search_teams_messages` - Search messages

### Other (3 tools)
- `search_contacts` - Search directory
- `list_recordings` - List meeting recordings
- `download_recording` - Download recording

**Total: 18 tools**

---

## 🎯 Success Criteria

### Functional
✅ All 15+ tools working
✅ 3+ resources defined
✅ 3+ prompt templates
✅ Works with Claude Desktop
✅ Seamless authentication

### Quality
✅ Test coverage >80%
✅ All tests passing
✅ Complete documentation
✅ No linting errors

### User Experience
✅ Installation straightforward
✅ Natural language queries work
✅ Response times <3 seconds
✅ Helpful error messages

---

## 🔒 Security Considerations

- Tokens stored with restrictive permissions (0o600)
- Input validation on all parameters
- No token logging
- HTTPS-only for Graph API
- Minimal OAuth scopes by default

---

## 📝 Testing Strategy

1. **Unit tests** - Mock Graph API, test each tool
2. **Integration tests** - Test MCP protocol, tool discovery
3. **Manual tests** - Test with Claude Desktop
4. **Performance tests** - Benchmark response times

Target coverage: **>80%**

---

## 🚧 Known Limitations & Future Work

### Current Limitations
- Personal OneDrive only (shared drives require admin consent)
- Basic error handling (will be improved)
- No caching (will add in Phase 6)

### Future Enhancements
- Real-time notifications via webhooks
- Batch operations (archive multiple emails)
- Advanced search with complex filters
- File content extraction (Excel, PDF, Word)
- Multi-tenant support (multiple accounts)

---

## 📚 Additional Resources

### External Documentation
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP Docs](https://gofastmcp.com/)
- [Claude Desktop MCP](https://docs.claude.com/en/docs/mcp)
- [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/api/overview)

### Example MCP Servers
- [GitHub MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/github)
- [Slack MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/slack)
- [Postgres MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/postgres)

---

## 💡 Tips for Implementation

1. **Start small** - Implement 2-3 tools first, validate approach
2. **Test frequently** - Don't wait until the end
3. **Use Claude Desktop early** - Best way to validate UX
4. **Keep CLI working** - Don't break existing functionality
5. **Document as you go** - Update docs when you add tools
6. **Ask for help** - Reference implementation plan when stuck

---

## 📞 Getting Help

If you get stuck during implementation:

1. Check the relevant section in **MCP_IMPLEMENTATION_PLAN.md**
2. Review the architecture in **MCP_ARCHITECTURE.md**
3. Look at examples in the [MCP Python SDK repo](https://github.com/modelcontextprotocol/python-sdk)
4. Check [MCP Specification](https://spec.modelcontextprotocol.io/) for protocol details
5. Ask on [MCP Discord](https://discord.gg/anthropic) (community support)

---

## 🎉 Let's Build!

Everything you need to implement the MCP server is in these docs. Follow the checklist, reference the plan for details, and check the architecture for design questions.

**Estimated timeline: 6-10 days**

Happy coding! 🚀

---

**Documentation Version:** 1.0
**Last Updated:** 2025-10-18
**Status:** Ready for Implementation
