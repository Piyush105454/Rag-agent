# Google Drive Integration Setup

To automatically sync documents from Google Drive into the RAG Knowledge Assistant, follow these steps to configure a Service Account.

## 1. Create a Service Account

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing one.
3. Navigate to **IAM & Admin > Service Accounts**.
4. Click **Create Service Account** and give it a name (e.g., ag-drive-sync).
5. Click **Done** (no special roles are needed).

## 2. Generate a Key

1. Click on the newly created service account.
2. Go to the **Keys** tab.
3. Click **Add Key > Create new key**.
4. Choose **JSON** and download the file.
5. Move this JSON file to a secure location on your server (e.g., /app/secrets/service_account.json).

## 3. Enable the Google Drive API

1. In the Google Cloud Console, go to **APIs & Services > Library**.
2. Search for **Google Drive API**.
3. Click **Enable.

## 4. Share Your Drive Folder

1. Open Google Drive and find the folder you want to index.
2. Right-click the folder and select **Share.
3. Share the folder with the email address of your Service Account (e.g., ag-drive-sync@your-project.iam.gserviceaccount.com).
4. Grant it **Viewer** access.

## 5. Configure the Application

1. Open .env.
2. Set GOOGLE_SERVICE_ACCOUNT_JSON to the absolute path of your downloaded JSON key.
3. Get the Folder ID from the Drive URL (the long string of characters after /folders/).
4. Set DRIVE_FOLDER_ID in .env to this ID.

## 6. Understanding Group Mapping

By default, the sync job maps subfolders directly to skill groups. For example:

- /Engineering/ -> access_group = engineering`n- /Sales/ -> access_group = sales`n
When the application runs, the APScheduler will automatically poll for changes in these folders every DRIVE_POLL_INTERVAL_MINUTES.