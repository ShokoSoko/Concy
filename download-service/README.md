# YouTube Download Service

This service runs yt-dlp to download YouTube videos and upload them to Vercel Blob storage.

## Deployment Options

### Option 1: Railway (Recommended)

1. Install Railway CLI: `npm i -g @railway/cli`
2. Login: `railway login`
3. Initialize: `railway init`
4. Add environment variable:
   \`\`\`bash
   railway variables set BLOB_READ_WRITE_TOKEN=your_token_here
   \`\`\`
5. Deploy: `railway up`
6. Get your service URL from Railway dashboard

### Option 2: Fly.io

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Launch app: `fly launch`
4. Set secret:
   \`\`\`bash
   fly secrets set BLOB_READ_WRITE_TOKEN=your_token_here
   \`\`\`
5. Deploy: `fly deploy`

### Option 3: Replit

1. Create new Repl, select "Python"
2. Upload these files to your Repl
3. Add Secret in Replit: `BLOB_READ_WRITE_TOKEN`
4. Run: `python main.py`
5. Use the Replit URL as your service endpoint

## Environment Variables

- `BLOB_READ_WRITE_TOKEN`: Your Vercel Blob storage token (from Vercel dashboard)

## Testing

\`\`\`bash
curl -X POST http://localhost:8000/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
\`\`\`

## Usage from Vercel App

Once deployed, update your Vercel app's environment variable:
\`\`\`
DOWNLOAD_SERVICE_URL=https://your-service.railway.app
