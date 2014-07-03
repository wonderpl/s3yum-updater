
## AWS resources

Use the example CloudFormation stack template to create the required AWS resources:
- S3 bucket to host the yum repository.
- SNS topic for update notifications.
- SQS queue subcribed to the topic.
- AWS credentials for `repoupdate-daemon`.
- AWS group & credentials for clients publishing to the repository.

```sh
make PACKAGE_BUCKET_NAME=packages.example.com aws-resources
sleep 30
aws cloudformation describe-stacks --stack-name packages --output text
```

## Initialize repositories on S3

The `repoupdate-daemon` can manage multiple yum repositories on S3 and doesn't need a local copy.
However the existing or new repositories do need to be copied to S3. To create an empty repository
for `development/x86_64` on the packages bucket use:

```sh
mkdir -p repos/development/x86_64
createrepo repos/development/x86_64
aws s3 sync repos s3://packages.example.com
```

## Install & configure repoupdate-daemon

Build and install the s3yum-updater rpm and then create the configuration files.
Start the `repoupdate-daemon` service.

```sh
make install
echo -e 'OPTIONS="$OPTIONS -b packages.example.com"\nexport AWS_CREDENTIAL_FILE=/etc/repoupdate-credentials.ini' |\
        sudo tee /etc/sysconfig/repoupdate-daemon
aws cloudformation describe-stacks --stack-name packages |\
        python -c 'import sys, json; print json.load(sys.stdin)["Stacks"][0]["Outputs"][0]["OutputValue"]' |\
        sudo tee /etc/repoupdate-credentials.ini
sudo service repoupdate-daemon start
```

If running the daemon on an EC2 instance, rather than using a credentials file, you should probably
use an IAM instance role with the appropriate policy.
See the policy for `PackageUpdateUser` in `cloudformation.json` as a template for the permissions required.

## Test package publish process

To test that the daemon is working correctly you can use the `publish-packages` command with
the credentials created by CloudFormation to publish the s3yum-updater rpm.

```sh
aws cloudformation describe-stacks --stack-name packages |\
        python -c 'import sys, json; print json.load(sys.stdin)["Stacks"][0]["Outputs"][1]["OutputValue"]' |\
        tee repopublish-credentials.ini
TOPIC=`aws sns list-topics --output text | awk '/packages-new/{ print $2 }'`
AWS_CREDENTIAL_FILE=repopublish-credentials.ini \
        publish-packages --bucket packages.example.com --sns-topic $TOPIC dist/noarch/s3yum-updater*.noarch.rpm
```

## Test yum access

If you enable public access (see the `PublicRepository` parameter in `cloudformation.json`) then you
can access the repository over http.
Try `curl http://packages.example.com.s3.amazonaws.com/development/x86_64/repodata/repomd.xml` to confirm.

Create `/etc/yum.repos.d/example.repo` to test:
```ini
[example]
name=example - $basearch
baseurl=http://packages.example.com.s3.amazonaws.com/development/$basearch
```

```sh
yum --disablerepo \* --enablerepo example list --showduplicates available
```

## yum-s3-iam

Rather than using a public repository, it's more likely that you'll want to keep your packages private
and access the content with the S3 protocol. To do that install the `s3iam` plugin.

```sh
git clone git@github.com:seporaitis/yum-s3-iam.git
sudo make -C yum-s3-iam install
```

Add `s3_enabled=1` to the repository configuration, `/etc/yum.repos.d/example.repo`:

```ini
[example]
name=example - $basearch
baseurl=http://packages.example.com.s3.amazonaws.com/development/$basearch
s3_enabled=1
```

