# NiFi Custom JARs

This folder is used to request new JAR files to be added to the custom NiFi Docker image.

## How to Add a New JAR

1. **Create a JSON manifest file** in this folder with the following format:

```json
{
    "name": "your-jar-name-1.0.0.jar",
    "url": "https://download-url/your-jar-name-1.0.0.jar",
    "install_path": "/opt/nifi/nifi-current/lib/",
    "description": "Description of what this JAR is for",
    "requested_by": "your-name",
    "reason": "Why this JAR is needed",
    "version": "1.0.0"
}
```

2. **Name the manifest file** with the same name as the JAR file but with `.json` extension:
   - JAR: `mysql-connector-j-9.5.0.jar`
   - Manifest: `mysql-connector-j-9.5.0.json`

3. **Create a Pull Request** with the manifest file

4. **Wait for approval and merge** - Once your PR is merged:
   - The CI pipeline will automatically detect the new JAR
   - A new PR will be created to update the Dockerfile
   - After that PR is approved, the Docker image will be built
   - Finally, a PR will be created to update the ECS task definition

## Supported JAR Locations

| Path | Use Case |
|------|----------|
| `/opt/nifi/nifi-current/lib/` | General NiFi libraries (JDBC drivers, etc.) |
| `/opt/nifi/nifi-current/extensions/` | NiFi custom processors and extensions |

## Example Manifest Files

### JDBC Driver Example
```json
{
    "name": "postgresql-42.7.1.jar",
    "url": "https://jdbc.postgresql.org/download/postgresql-42.7.1.jar",
    "install_path": "/opt/nifi/nifi-current/lib/",
    "description": "PostgreSQL JDBC Driver",
    "requested_by": "john.doe",
    "reason": "Required for PostgreSQL database connections",
    "version": "42.7.1"
}
```

### Maven Repository Example
```json
{
    "name": "aws-java-sdk-s3-1.12.500.jar",
    "url": "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-s3/1.12.500/aws-java-sdk-s3-1.12.500.jar",
    "install_path": "/opt/nifi/nifi-current/lib/",
    "description": "AWS S3 SDK for NiFi S3 operations",
    "requested_by": "jane.doe",
    "reason": "Enhanced S3 functionality",
    "version": "1.12.500"
}
```

## Pipeline Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Developer adds  │     │ CI detects new  │     │ PR created to   │
│ JAR manifest    │────▶│ JAR manifest    │────▶│ update          │
│ + creates PR    │     │ file            │     │ Dockerfile      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ ECS Task Def    │     │ Docker image    │     │ Dockerfile PR   │
│ updated +       │◀────│ built + pushed  │◀────│ approved +      │
│ deployed        │     │ to ECR          │     │ merged          │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Important Notes

- Only JARs from trusted sources (Maven Central, official vendor sites) are allowed
- JARs must be compatible with the NiFi version in use
- Large JARs may increase Docker image build time
- Always specify the exact version in the manifest

## Troubleshooting

### JAR not being detected
- Ensure the manifest file has `.json` extension
- Verify the JSON syntax is valid
- Check that all required fields are present

### Build failures
- Verify the download URL is accessible
- Ensure the JAR file exists at the specified URL
- Check for any network/firewall restrictions
