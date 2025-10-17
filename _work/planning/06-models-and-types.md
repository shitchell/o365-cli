# Pydantic Models and Type Resolution

## Overview

Use Pydantic for:
- **Type safety** and validation
- **Structured data** from Graph API
- **Flexible input resolution** (e.g., `Userish` pattern)
- **Consistent serialization** (JSON, dict, etc.)
- **Self-documenting** code with type hints

## Pydantic Setup

### Dependencies

```toml
[project]
dependencies = [
    "python-dateutil>=2.8.0",
    "html2text>=2020.1.16",
    "pydantic>=2.0.0",
    "wcwidth>=0.2.5",
]
```

### Base Configuration

```python
# o365/models/base.py
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List

class O365BaseModel(BaseModel):
    """Base model for all O365 entities"""

    model_config = ConfigDict(
        # Allow extra fields from API (future-proofing)
        extra='ignore',
        # Use by_alias for API field names
        populate_by_name=True,
        # Validate on assignment
        validate_assignment=True,
    )

    def to_dict(self) -> dict:
        """Convert to dictionary (for API requests)"""
        return self.model_dump(by_alias=True, exclude_none=True)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return self.model_dump_json(by_alias=True, exclude_none=True)

    @classmethod
    def from_graph_response(cls, data: dict):
        """Create from Graph API response"""
        return cls.model_validate(data)
```

## Core Models

### User Model

```python
# o365/models/user.py
from pydantic import EmailStr, Field
from typing import Optional
from .base import O365BaseModel

class User(O365BaseModel):
    """Represents an Office365 user"""

    id: str = Field(..., description="User's unique ID")
    email: EmailStr = Field(..., alias='mail', description="Primary email address")
    display_name: str = Field(..., alias='displayName')
    given_name: Optional[str] = Field(None, alias='givenName')
    surname: Optional[str] = Field(None, alias='surname')
    user_principal_name: str = Field(..., alias='userPrincipalName')
    job_title: Optional[str] = Field(None, alias='jobTitle')
    department: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.display_name} <{self.email}>"

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"

    @property
    def domain(self) -> str:
        """Get user's email domain"""
        return self.email.split('@')[1].lower()

    def is_external_to(self, domain: str) -> bool:
        """Check if user is from different domain"""
        return self.domain != domain.lower()
```

### Email Models

```python
# o365/models/mail.py
from pydantic import EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from .base import O365BaseModel
from .user import User

class EmailAddress(O365BaseModel):
    """Email address with optional name"""
    address: EmailStr
    name: Optional[str] = None

    def __str__(self) -> str:
        if self.name:
            return f"{self.name} <{self.address}>"
        return self.address

class Attachment(O365BaseModel):
    """Email attachment"""
    id: str
    name: str
    content_type: str = Field(..., alias='contentType')
    size: int
    is_inline: bool = Field(False, alias='isInline')
    content_id: Optional[str] = Field(None, alias='contentId')

    @property
    def is_image(self) -> bool:
        return self.content_type.startswith('image/')

    @property
    def extension(self) -> str:
        return self.name.split('.')[-1].lower() if '.' in self.name else ''

class EmailMessage(O365BaseModel):
    """Represents an email message"""

    id: str
    subject: Optional[str] = None
    body_preview: str = Field('', alias='bodyPreview')
    from_address: EmailAddress = Field(..., alias='from')
    to_recipients: List[EmailAddress] = Field(default_factory=list, alias='toRecipients')
    cc_recipients: List[EmailAddress] = Field(default_factory=list, alias='ccRecipients')
    received_datetime: datetime = Field(..., alias='receivedDateTime')
    is_read: bool = Field(False, alias='isRead')
    has_attachments: bool = Field(False, alias='hasAttachments')
    attachments: List[Attachment] = Field(default_factory=list)
    body: Optional[dict] = None  # {contentType: 'html'|'text', content: str}

    @property
    def sender(self) -> str:
        """Get sender as formatted string"""
        return str(self.from_address)

    @property
    def real_attachments(self) -> List[Attachment]:
        """Get non-inline attachments only"""
        return [att for att in self.attachments if not att.is_inline]

    @property
    def inline_attachments(self) -> List[Attachment]:
        """Get inline attachments (usually images)"""
        return [att for att in self.attachments if att.is_inline]

    def is_external(self, user_domain: str) -> bool:
        """Check if sender is from outside organization"""
        sender_domain = self.from_address.address.split('@')[1].lower()
        return sender_domain != user_domain.lower()
```

### Calendar Models

```python
# o365/models/calendar.py
from pydantic import Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
from .base import O365BaseModel

class ResponseStatus(str, Enum):
    """Meeting response status"""
    NONE = 'none'
    ORGANIZER = 'organizer'
    TENTATIVELY_ACCEPTED = 'tentativelyAccepted'
    ACCEPTED = 'accepted'
    DECLINED = 'declined'
    NOT_RESPONDED = 'notResponded'

class EventAttendee(O365BaseModel):
    """Event attendee"""
    email: str = Field(..., alias='emailAddress.address')
    name: Optional[str] = Field(None, alias='emailAddress.name')
    response_status: ResponseStatus = Field(..., alias='status.response')

class CalendarEvent(O365BaseModel):
    """Calendar event"""

    id: str
    subject: str
    start: datetime = Field(..., alias='start.dateTime')
    end: datetime = Field(..., alias='end.dateTime')
    location: Optional[str] = Field(None, alias='location.displayName')
    organizer: str = Field(..., alias='organizer.emailAddress.address')
    organizer_name: Optional[str] = Field(None, alias='organizer.emailAddress.name')
    attendees: List[EventAttendee] = Field(default_factory=list)
    is_all_day: bool = Field(False, alias='isAllDay')
    is_cancelled: bool = Field(False, alias='isCancelled')
    response_status: ResponseStatus = Field(..., alias='responseStatus.response')
    body_preview: Optional[str] = Field(None, alias='bodyPreview')

    @property
    def needs_response(self) -> bool:
        """Check if user needs to respond"""
        return self.response_status == ResponseStatus.NOT_RESPONDED

    @property
    def is_organizer(self) -> bool:
        """Check if current user is organizer"""
        return self.response_status == ResponseStatus.ORGANIZER

    @property
    def duration_minutes(self) -> int:
        """Get event duration in minutes"""
        return int((self.end - self.start).total_seconds() / 60)
```

### Chat Models

```python
# o365/models/chat.py
from pydantic import Field
from typing import Optional, List
from datetime import datetime
from .base import O365BaseModel

class ChatMember(O365BaseModel):
    """Chat participant"""
    id: str
    display_name: str = Field(..., alias='displayName')
    email: Optional[str] = None

class ChatMessage(O365BaseModel):
    """Teams chat message"""

    id: str
    created_datetime: datetime = Field(..., alias='createdDateTime')
    from_user: Optional[ChatMember] = Field(None, alias='from')
    body: str = Field(..., alias='body.content')
    message_type: str = Field('message', alias='messageType')

class Chat(O365BaseModel):
    """Teams chat"""

    id: str
    topic: Optional[str] = None
    created_datetime: datetime = Field(..., alias='createdDateTime')
    last_updated: datetime = Field(..., alias='lastUpdatedDateTime')
    chat_type: str = Field(..., alias='chatType')  # oneOnOne, group
    members: List[ChatMember] = Field(default_factory=list)

    @property
    def is_one_on_one(self) -> bool:
        return self.chat_type == 'oneOnOne'

    @property
    def display_name(self) -> str:
        """Get chat display name"""
        if self.topic:
            return self.topic
        if self.is_one_on_one and self.members:
            return self.members[0].display_name
        return f"Group chat ({len(self.members)} members)"
```

### File Models

```python
# o365/models/files.py
from pydantic import Field
from typing import Optional
from datetime import datetime
from .base import O365BaseModel

class DriveItem(O365BaseModel):
    """OneDrive/SharePoint file or folder"""

    id: str
    name: str
    size: int = 0
    created_datetime: datetime = Field(..., alias='createdDateTime')
    modified_datetime: datetime = Field(..., alias='lastModifiedDateTime')
    web_url: str = Field(..., alias='webUrl')
    download_url: Optional[str] = Field(None, alias='@microsoft.graph.downloadUrl')
    is_folder: bool = Field(False, alias='folder')
    created_by: Optional[str] = Field(None, alias='createdBy.user.displayName')
    modified_by: Optional[str] = Field(None, alias='lastModifiedBy.user.displayName')

    @property
    def is_file(self) -> bool:
        return not self.is_folder

    @property
    def extension(self) -> str:
        if self.is_folder:
            return ''
        return self.name.split('.')[-1].lower() if '.' in self.name else ''

    @property
    def file_type(self) -> str:
        """Get human-readable file type"""
        if self.is_folder:
            return 'DIR'

        ext_map = {
            'docx': 'DOCX', 'doc': 'DOC',
            'xlsx': 'XLSX', 'xls': 'XLS',
            'pptx': 'PPTX', 'ppt': 'PPT',
            'pdf': 'PDF',
            'txt': 'TXT',
            'md': 'MD',
            'png': 'PNG', 'jpg': 'JPG', 'jpeg': 'JPG', 'gif': 'GIF',
        }

        return ext_map.get(self.extension, self.extension.upper() or 'FILE')
```

## Resolver Pattern ("Ish" Types)

### Userish - Flexible User Resolution

```python
# o365/models/resolvers.py
from typing import Optional, List, Union
from pydantic import BaseModel, validator
from .user import User
from .base import GraphClient

class ResolutionError(Exception):
    """Raised when resolution fails or is ambiguous"""
    pass

class Userish(BaseModel):
    """Flexible user reference that can be resolved to a User

    Accepts:
    - Email address: "john.doe@company.com"
    - Display name: "John Doe"
    - First name: "john"
    - User ID: "a1b2c3d4-..."
    - User object: User(...)

    Similar to Git's "committish" - flexible input that resolves to concrete object.
    """

    query: Union[str, User]
    _resolved: Optional[User] = None
    _client: Optional[GraphClient] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, query: Union[str, User], client: Optional[GraphClient] = None):
        super().__init__(query=query)
        self._client = client

    def resolve(self, client: Optional[GraphClient] = None) -> User:
        """Resolve to a concrete User object

        Raises:
            ResolutionError: If user not found or query is ambiguous

        Returns:
            User object
        """
        # Already resolved
        if self._resolved:
            return self._resolved

        # Already a User object
        if isinstance(self.query, User):
            self._resolved = self.query
            return self._resolved

        # Use provided client or stored client
        client = client or self._client
        if not client:
            raise ResolutionError("No Graph API client provided for resolution")

        # Try different resolution strategies
        query = self.query.strip()

        # 1. Try as exact email
        if '@' in query:
            user = self._resolve_by_email(client, query)
            if user:
                self._resolved = user
                return user

        # 2. Try as user ID (UUID format)
        if self._looks_like_uuid(query):
            user = self._resolve_by_id(client, query)
            if user:
                self._resolved = user
                return user

        # 3. Try as display name or partial match
        users = self._search_users(client, query)

        if len(users) == 0:
            raise ResolutionError(f"No user found matching '{query}'")

        if len(users) == 1:
            self._resolved = users[0]
            return users[0]

        # Multiple matches - ambiguous
        matches = '\n'.join([f"  - {u.display_name} <{u.email}>" for u in users])
        raise ResolutionError(
            f"Ambiguous user query '{query}' matches {len(users)} users:\n{matches}\n"
            f"Please be more specific (use full email or ID)"
        )

    def resolve_or_none(self, client: Optional[GraphClient] = None) -> Optional[User]:
        """Try to resolve, return None on failure instead of raising"""
        try:
            return self.resolve(client)
        except ResolutionError:
            return None

    @staticmethod
    def _looks_like_uuid(s: str) -> bool:
        """Check if string looks like a UUID"""
        import re
        uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
        return bool(re.match(uuid_pattern, s.lower()))

    @staticmethod
    def _resolve_by_email(client: GraphClient, email: str) -> Optional[User]:
        """Resolve by exact email match"""
        try:
            data = client.get(f'/users/{email}')
            return User.from_graph_response(data)
        except Exception:
            return None

    @staticmethod
    def _resolve_by_id(client: GraphClient, user_id: str) -> Optional[User]:
        """Resolve by user ID"""
        try:
            data = client.get(f'/users/{user_id}')
            return User.from_graph_response(data)
        except Exception:
            return None

    @staticmethod
    def _search_users(client: GraphClient, query: str) -> List[User]:
        """Search for users by display name or email"""
        try:
            # Search by display name or email (case-insensitive)
            filter_query = (
                f"startswith(displayName, '{query}') or "
                f"startswith(givenName, '{query}') or "
                f"startswith(surname, '{query}') or "
                f"startswith(mail, '{query}')"
            )

            data = client.get(f'/users?$filter={filter_query}&$top=25')
            users = [User.from_graph_response(u) for u in data.get('value', [])]

            # If no results with startswith, try contains
            if not users:
                search_query = f'"{query}"'
                data = client.get(f'/users?$search={search_query}&$top=25',
                                headers={'ConsistencyLevel': 'eventual'})
                users = [User.from_graph_response(u) for u in data.get('value', [])]

            return users
        except Exception:
            return []

    def __str__(self) -> str:
        if isinstance(self.query, User):
            return str(self.query)
        return f"Userish({self.query!r})"

    def __repr__(self) -> str:
        return f"Userish(query={self.query!r}, resolved={self._resolved is not None})"
```

### Folderish - Flexible Folder Resolution

```python
class Folderish(BaseModel):
    """Flexible folder reference (Inbox, Archive, folder ID, folder path)"""

    query: str
    _resolved_id: Optional[str] = None

    WELL_KNOWN_FOLDERS = {
        'inbox': 'inbox',
        'sent': 'sentitems',
        'drafts': 'drafts',
        'archive': 'archive',
        'deleted': 'deleteditems',
        'junk': 'junkemail',
    }

    def resolve(self, client: GraphClient) -> str:
        """Resolve to folder ID"""
        if self._resolved_id:
            return self._resolved_id

        query_lower = self.query.lower()

        # Check well-known folders first
        if query_lower in self.WELL_KNOWN_FOLDERS:
            self._resolved_id = self.WELL_KNOWN_FOLDERS[query_lower]
            return self._resolved_id

        # Try as folder ID directly
        if self._looks_like_folder_id(self.query):
            self._resolved_id = self.query
            return self._resolved_id

        # Search by display name
        folders = self._search_folders(client, self.query)

        if len(folders) == 0:
            raise ResolutionError(f"No folder found matching '{self.query}'")

        if len(folders) == 1:
            self._resolved_id = folders[0]['id']
            return self._resolved_id

        # Ambiguous
        matches = '\n'.join([f"  - {f['displayName']}" for f in folders])
        raise ResolutionError(
            f"Ambiguous folder query '{self.query}' matches {len(folders)} folders:\n{matches}"
        )

    @staticmethod
    def _looks_like_folder_id(s: str) -> bool:
        """Check if looks like Graph API folder ID"""
        return len(s) > 50 and s.startswith('AAMk')

    @staticmethod
    def _search_folders(client: GraphClient, query: str) -> List[dict]:
        """Search folders by name"""
        data = client.get('/me/mailFolders')
        folders = data.get('value', [])
        return [f for f in folders if query.lower() in f.get('displayName', '').lower()]
```

## Usage Examples

### In Controllers

```python
# controllers/calendar.py
from ..models.resolvers import Userish
from ..models.calendar import CalendarEvent

class CalendarController(BaseController):
    def list_events(self):
        """List calendar events"""

        # Resolve user if specified
        if self.args.user:
            try:
                userish = Userish(self.args.user, client=self.model.client)
                user = userish.resolve()
                print(f"Viewing calendar for: {user}")
                events = self.model.get_events(user_id=user.id)
            except ResolutionError as e:
                self.error(str(e))
                return
        else:
            events = self.model.get_events()

        # Display events
        for event in events:
            print(self.view.format_event(event))
```

### In Models

```python
# models/calendar.py
class CalendarModel(BaseModel):
    def get_events(self, user_id: Optional[str] = None, ...) -> List[CalendarEvent]:
        """Get calendar events"""

        if user_id:
            url = f'/users/{user_id}/calendar/events'
        else:
            url = '/me/calendar/events'

        # ... build query

        data = self.client.get(url)

        # Parse into Pydantic models
        return [CalendarEvent.from_graph_response(event)
                for event in data.get('value', [])]
```

### In Views

```python
# views/calendar.py
class CalendarView(BaseView):
    def format_event(self, event: CalendarEvent) -> str:
        """Format calendar event"""

        # Type hints help IDE autocomplete
        start_time = event.start.strftime('%H:%M')
        end_time = event.end.strftime('%H:%M')

        if self.is_tty:
            parts = [
                self.icon('time'),
                self.color('date', f"{start_time} - {end_time}"),
                self.color('subject', event.subject)
            ]
        else:
            parts = [
                f"[{start_time}-{end_time}]",
                event.subject
            ]

        # ... rest of formatting
```

## Benefits

### Type Safety
```python
# IDE knows event is CalendarEvent
event: CalendarEvent = model.get_event(event_id)

# Autocomplete works
event.subject  # ✓
event.start    # ✓
event.foo      # ✗ Error: CalendarEvent has no attribute 'foo'
```

### Validation
```python
# Pydantic validates on creation
message = EmailMessage(
    id='123',
    subject='Test',
    from_address={'address': 'invalid-email'},  # ✗ ValidationError: invalid email
)
```

### Flexible Resolution
```python
# All of these work:
calendar --user "john"
calendar --user "john.doe@company.com"
calendar --user "a1b2c3d4-..."

# Clear error for ambiguous input:
calendar --user "j"
# Error: Ambiguous user query 'j' matches 5 users:
#   - John Doe <john.doe@company.com>
#   - Jane Smith <jane.smith@company.com>
#   ...
```

### JSON Export
```python
# Easy serialization for --format json
messages = model.get_messages()
for msg in messages:
    print(msg.to_json())  # Valid JSON output
```

## Testing

### Model Tests

```python
# tests/test_models/test_mail.py
def test_email_message_parsing():
    """Test parsing Graph API response into EmailMessage"""
    api_response = {
        'id': '123',
        'subject': 'Test',
        'from': {'address': 'sender@test.com', 'name': 'Sender'},
        'receivedDateTime': '2025-10-17T14:23:00Z',
        'isRead': False,
    }

    msg = EmailMessage.from_graph_response(api_response)

    assert msg.id == '123'
    assert msg.subject == 'Test'
    assert msg.from_address.address == 'sender@test.com'
    assert not msg.is_read

def test_email_external_detection():
    """Test external sender detection"""
    msg = EmailMessage(
        id='123',
        from_address={'address': 'external@other.com'},
        receivedDateTime='2025-10-17T14:23:00Z'
    )

    assert msg.is_external('company.com')
    assert not msg.is_external('other.com')
```

### Resolver Tests

```python
# tests/test_models/test_resolvers.py
def test_userish_resolution_by_email(mock_client):
    """Test resolving user by email"""
    mock_client.get.return_value = {
        'id': 'user123',
        'mail': 'john@company.com',
        'displayName': 'John Doe',
        'userPrincipalName': 'john@company.com'
    }

    userish = Userish('john@company.com', client=mock_client)
    user = userish.resolve()

    assert user.email == 'john@company.com'
    assert user.display_name == 'John Doe'

def test_userish_ambiguous_query(mock_client):
    """Test error on ambiguous query"""
    mock_client.get.return_value = {
        'value': [
            {'id': '1', 'mail': 'john1@company.com', 'displayName': 'John One'},
            {'id': '2', 'mail': 'john2@company.com', 'displayName': 'John Two'},
        ]
    }

    userish = Userish('john', client=mock_client)

    with pytest.raises(ResolutionError) as exc:
        userish.resolve()

    assert 'Ambiguous' in str(exc.value)
    assert 'John One' in str(exc.value)
```

## Migration Notes

1. Add Pydantic to dependencies
2. Create base model class first
3. Migrate models one at a time
4. Update controllers to use new models
5. Add resolver classes
6. Update argument parsing to use resolvers
7. Write comprehensive tests

This provides a solid foundation for type-safe, validated data handling!
