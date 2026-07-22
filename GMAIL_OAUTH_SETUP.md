# Gmail OAuth delivery setup

Kompliance supports Gmail through the Gmail API and requests only
`https://www.googleapis.com/auth/gmail.send`. It does not need the Gmail account
password and cannot read or delete mailbox content with this scope.

## Google Cloud setup

1. Create or select a Google Cloud project and enable the Gmail API.
2. Configure the OAuth consent screen. Add the sending Gmail address as a test
   user while the app is in Testing.
3. Create an OAuth client with application type **Desktop app**.
4. Download its JSON into a private local folder. The repository ignores common
   OAuth client filenames, but the file should still be moved outside Git.
5. From this repository, run:

   ```powershell
   python gmail_oauth_setup.py C:\private\client_secret.json `
     --sender your-address@gmail.com `
     --output .env.gmail.oauth
   ```

6. Sign in to the intended sender account and approve only **Send email on your
   behalf**. Copy the generated values to the server's untracked `.env`.
7. Keep `KOMPLIANCE_EMAIL_DELIVERY=0` and `KOMPLIANCE_SCHEDULER=0` for deployment.
   First verify configuration and send one controlled message to an approved
   recipient. Enable scheduling only after that message is accepted.

Required deployment values:

```dotenv
KOMPLIANCE_EMAIL_PROVIDER=gmail_oauth
KOMPLIANCE_SMTP_FROM=your-address@gmail.com
KOMPLIANCE_GMAIL_CLIENT_ID=
KOMPLIANCE_GMAIL_CLIENT_SECRET=
KOMPLIANCE_GMAIL_REFRESH_TOKEN=
KOMPLIANCE_BASE_URL=https://your-kompliance-host.example
KOMPLIANCE_EMAIL_DELIVERY=0
```

Never commit the OAuth JSON, client secret, refresh token, generated environment
file, Gmail password, or access tokens. Revoke the OAuth grant immediately if a
token may have been exposed.

## Testing versus production

For an External consent screen in **Testing**, Google expires authorizations and
offline refresh tokens after seven days for Gmail scopes. Move the consent screen
to Production before relying on unattended delivery. Google may require extra
consent-screen details or verification depending on the users and rollout.

Official references:

- <https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send>
- <https://developers.google.com/identity/protocols/oauth2>
- <https://developers.google.com/identity/protocols/oauth2/resources/best-practices>
