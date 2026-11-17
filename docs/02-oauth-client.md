# 02. Create the OAuth client

## Why

When someone clicks Connect in Claude, they sign in with Google. Google needs to know which app is asking, and that app is identified by an OAuth client (a client ID plus a client secret).

## Steps

### 1. Create a Web application client

In the console go to **Google Auth Platform**, then **Clients**, then **Create client**.

- **Application type:** Web application. A Desktop type client does not work behind a server side OAuth proxy.
- **Name:** anything, for example `<web-client-name>`. Keep it separate from any other MCP's client, so you can rotate one without breaking the other.
- **Authorized redirect URIs:** leave empty for now. The URL is only known after the deploy in step 03.

Click **Create**.

### 2. Save the client secret straight away

The confirmation dialog shows the **client ID** and **client secret**. Google does not show the secret again after you close this dialog.

- Copy the secret (it starts with `GOCSPX-` and is 35 characters long) into a password manager, or click **Download JSON**.
- The client ID can be found again later. It is also in the page URL when you open the client.

### 3. Note the client ID

It looks like `<numbers>-<letters>.apps.googleusercontent.com` and appears as `<client-id>` in step 03.

## Gotcha

If you download the JSON, it contains more than the secret (`client_id`, `project_id`, `auth_uri` and so on). In step 03 you only paste the `GOCSPX-...` value, not the whole file. I got this wrong, see [05. Client secret fix](05-client-secret-fix.md).

## Next

[03. Deploy the server to Cloud Run](03-deploy-cloud-run.md)
