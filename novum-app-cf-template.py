"""Generating CloudFormation template."""

from ipaddress import ip_network

from ipify import get_ip

from troposphere import (
    Base64,
    ec2,
    GetAtt,
    Join,
    Output,
    Parameter,
    Ref,
    Template,
)

from troposphere.iam import (
    InstanceProfile,
    PolicyType as IAMPolicy,
    Role,
)

from awacs.aws import (
    Action,
    Allow,
    Policy,
    Principal,
    Statement,
)

from awacs.sts import (
    AssumeRole
)

ApplicationName = "novum-app"
ApplicationPort = "3000"

GithubAccount = "tsyork"
GithubAnsibleURL = "https://github.com/{}/ansible".format(GithubAccount)

AnsiblePullCmd = \
    "/usr/local/bin/ansible-pull -U {} {}.yml -i localhost".format(
        GithubAnsibleURL,
        ApplicationName
    )

PublicCidrIp = str(ip_network(get_ip()))

t = Template()
t.add_description("Novum Application")

t.add_parameter(Parameter(
    "KeyPair",
    Description="Name of an existing EC2 KeyPair to SSH",
    Type="AWS::EC2::KeyPair::KeyName",
    ConstraintDescription="must be the name of an existing EC2 KeyPair.",
))

t.add_resource(ec2.SecurityGroup(
    "SecurityGroup",
    GroupDescription="Allow SSH and TCP/{} access".format(ApplicationPort),
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="22",
            ToPort="22",
            CidrIp=PublicCidrIp,
        ),
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort=ApplicationPort,
            ToPort=ApplicationPort,
            CidrIp="0.0.0.0/0",
        ),
    ],
))

ud = Base64(Join('\n', [
    "#!/bin/bash",
    "yum install --enablerepo=epel -y git",
    "pip install ansible",
    "curl --silent --location https://rpm.nodesource.com/setup_7.x | bash -",
    "yum -y install nodejs npm",
    AnsiblePullCmd,
    "echo '*/10 * * * * {}' > /etc/cron.d/ansible-pull".format(AnsiblePullCmd)
]))

t.add_resource(Role(
    "Role",
    AssumeRolePolicyDocument=Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Action=[AssumeRole],
                Principal=Principal("Service", ["ec2.amazonaws.com"])
            )
        ]
    )
))

t.add_resource(InstanceProfile(
    "InstanceProfile",
    Path="/",
    Roles=[Ref("Role")]
))

t.add_resource(IAMPolicy(
    "Policy",
    PolicyName="AllowS3",
    PolicyDocument=Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Action=[Action("s3", "*")],
                Resource=["*"])
        ]
    ),
    Roles=[Ref("Role")]
))

t.add_resource(ec2.Instance(
    "instance",
    ImageId="ami-15e9c770",
    InstanceType="t2.large",
    SecurityGroups=[Ref("SecurityGroup")],
    KeyName=Ref("KeyPair"),
    UserData=ud,
    IamInstanceProfile=Ref("InstanceProfile"),
))

t.add_output(Output(
    "InstancePublicIp",
    Description="Public IP of our instance.",
    Value=GetAtt("instance", "PublicIp"),
))

t.add_output(Output(
    "WebUrl",
    Description="Application endpoint",
    Value=Join("", [
        "http://", GetAtt("instance", "PublicDnsName"),
        ":", ApplicationPort
    ]),
))

print t.to_json()