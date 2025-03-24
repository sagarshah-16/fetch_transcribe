# GitHub Actions Deployment Setup

This repository is configured with automatic deployment to an SSH server using GitHub Actions.

## Required Secrets

To set up the deployment workflow, you need to add the following secrets to your GitHub repository:

### 1. `SSH_PRIVATE_KEY`

The SSH private key for authenticating with your server.

1. Generate a new SSH key pair specifically for deployment:
   ```bash
   ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy_key
   ```
2. Add the public key to the authorized_keys file on your server:
   ```bash
   cat ~/.ssh/github_deploy_key.pub >> ~/.ssh/authorized_keys
   ```
3. Copy the private key content and add it as the `SSH_PRIVATE_KEY` secret in GitHub:
   ```bash
   cat ~/.ssh/github_deploy_key
   ```

### 2. `SSH_KNOWN_HOSTS`

The SSH known hosts entry for your server to prevent man-in-the-middle attacks.

1. Generate the known_hosts entry:
   ```bash
   ssh-keyscan -H your-server-ip-or-domain
   ```
2. Copy the output and add it as the `SSH_KNOWN_HOSTS` secret in GitHub.

### 3. `SSH_USER`

The username to use when connecting to your SSH server.

### 4. `SERVER_IP`

The IP address or domain name of your SSH server.

### 5. `DEPLOY_PATH`

The absolute path on your server where the application should be deployed.

## Adding Secrets to GitHub

1. Go to your GitHub repository
2. Click on "Settings"
3. In the left sidebar, click on "Secrets and variables" → "Actions"
4. Click on "New repository secret" and add each of the required secrets

## Customizing the Deployment

You may need to customize the deployment process based on your specific requirements:

1. Modify `.github/workflows/deploy.yml` to:
   - Adjust Python version
   - Add custom deployment steps
   - Configure service restart commands
   - Exclude additional files/directories during rsync

2. Set up any necessary environment variables on your server or GitHub Actions.