# AWS Deployment Guide

## Prerequisites

Before deploying CloudSync to AWS, ensure you have:

- AWS CLI v2+ installed and configured
- Docker installed locally (v20.10+)
- Access to the CloudSync ECR repository
- IAM permissions for ECS, ECR, and VPC management
- A registered domain name (for SSL certificate)

## Architecture Overview

Internet → Route53 → CloudFront → ALB → ECS (Fargate) → RDS/ElastiCache

## Step-by-Step Deployment

### 1. Build and Push Docker Image

Login to ECR:
```
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

Build the image:
```
docker build -t cloudsync-api:latest .
docker tag cloudsync-api:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/cloudsync-api:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/cloudsync-api:latest
```

Dockerfile Best Practices:
- Use multi-stage builds
- Run as non-root user
- Include health checks
- Set appropriate resource limits

### 2. Create ECS Cluster

Using AWS CLI:
```
aws ecs create-cluster \
  --cluster-name cloudsync-production \
  --capacity-providers FARGATE FARGATE_SPOT \
  --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1,base=1 capacityProvider=FARGATE_SPOT,weight=3
```

Task Definition Configuration:
- CPU: 512 (0.5 vCPU)
- Memory: 1024 MB (1 GB)
- Network mode: awsvpc
- Requires compatibility: FARGATE
- Execution role: ecsTaskExecutionRole
- Task role: ecsTaskRole

Container Definition:
- Port mapping: 8000 TCP
- Environment variables: AWS_REGION, LOG_LEVEL
- Secrets from AWS Secrets Manager
- Log driver: awslogs to CloudWatch
- Health check: HTTP endpoint /health

### 3. Configure Application Load Balancer

Create ALB:
```
aws elbv2 create-load-balancer \
  --name cloudsync-alb \
  --subnets subnet-12345 subnet-67890 \
  --security-groups sg-12345 \
  --scheme internet-facing \
  --type application
```

Create target group:
```
aws elbv2 create-target-group \
  --name cloudsync-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-12345 \
  --target-type ip \
  --health-check-path /health
```

Create HTTPS listener:
```
aws elbv2 create-listener \
  --load-balancer-arn <alb-arn> \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=<cert-arn> \
  --default-actions Type=forward,TargetGroupArn=<tg-arn>
```

Security Group Rules:
- Inbound: 443 from 0.0.0.0/0, 80 from 0.0.0.0/0 (redirect to 443)
- Outbound: All traffic to VPC CIDR

### 4. Deploy ECS Service

Create service:
```
aws ecs create-service \
  --cluster cloudsync-production \
  --service-name cloudsync-api \
  --task-definition cloudsync-api:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345,subnet-67890],securityGroups=[sg-12345],assignPublicIp=ENABLED}" \
  --load-balancers targetGroupArn=<tg-arn>,containerName=cloudsync-api,containerPort=8000 \
  --health-check-grace-period 60
```

Auto-scaling:
```
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/cloudsync-production/cloudsync-api \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10
```

Target tracking on CPU utilization:
```
aws application-autoscaling put-scaling-policy \
  --policy-name cpu-autoscaling \
  --service-namespace ecs \
  --resource-id service/cloudsync-production/cloudsync-api \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-config.json
```

### 5. Database Setup (RDS)

Create PostgreSQL instance:
```
aws rds create-db-instance \
  --db-instance-identifier cloudsync-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 14.9 \
  --allocated-storage 100 \
  --storage-type gp3 \
  --master-username cloudsync_admin \
  --master-user-password <strong-password> \
  --vpc-security-group-ids sg-rds-12345 \
  --db-subnet-group-name cloudsync-db-subnet \
  --backup-retention-period 7 \
  --preferred-backup-window 03:00-04:00 \
  --enable-performance-insights \
  --performance-insights-retention-period 7 \
  --enable-cloudwatch-logs-exports '["postgresql"]' \
  --deletion-protection
```

Store connection string in Secrets Manager:
```
aws secretsmanager create-secret \
  --name cloudsync/production/database-url \
  --secret-string "postgresql://cloudsync_admin:<password>@<endpoint>:5432/cloudsync"
```

### 6. Redis Setup (ElastiCache)

Create Redis cluster:
```
aws elasticache create-replication-group \
  --replication-group-id cloudsync-redis \
  --replication-group-description "CloudSync Redis cluster" \
  --num-node-groups 1 \
  --replicas-per-node-group 1 \
  --node-type cache.t3.micro \
  --engine redis \
  --engine-version 7.0 \
  --port 6379 \
  --automatic-failover-enabled \
  --multi-az-enabled \
  --at-restEncryption-enabled \
  --transit-encryption-enabled \
  --cache-subnet-group-name cloudsync-redis-subnet
```

### 7. S3 Bucket Setup

Create bucket:
```
aws s3api create-bucket \
  --bucket cloudsync-prod-files \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket cloudsync-prod-files \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket cloudsync-prod-files \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

### 8. Monitoring Setup (CloudWatch)

Create log group:
```
aws logs create-log-group --log-group-name /ecs/cloudsync-api
aws logs put-retention-policy --log-group-name /ecs/cloudsync-api --retention-in-days 30
```

Create alarms:
- CPU utilization > 80%
- Memory utilization > 85%
- Error rate > 1%
- Healthy host count < desired count

### 9. SSL Certificate (ACM)

Request certificate:
```
aws acm request-certificate \
  --domain-name api.cloudsync.com \
  --validation-method DNS \
  --subject-alternative-names www.api.cloudsync.com
```

Validate via DNS records in Route53, then use certificate ARN in ALB HTTPS listener.

### 10. DNS Setup (Route53)

Create hosted zone and A record:
```
aws route53 change-resource-record-sets \
  --hosted-zone-id <zone-id> \
  --change-batch file://dns-changes.json
```

Point A record to ALB DNS name with alias.

## Environment Variables in Production

Required secrets in AWS Secrets Manager:
- DATABASE_URL
- REDIS_URL
- JWT_SECRET
- GROQ_API_KEY
- AWS credentials (if not using IAM roles)

Reference in ECS task definition using valueFrom.

## Deployment Verification

Check service status:
```
aws ecs describe-services \
  --cluster cloudsync-production \
  --services cloudsync-api
```

Test endpoints:
```
curl https://api.cloudsync.com/health
curl https://api.cloudsync.com/api/v1/query \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "test deployment"}'
```

## Troubleshooting

### Service won't start
- Check CloudWatch logs: /ecs/cloudsync-api
- Verify security group allows traffic
- Check task definition for missing env vars
- Review IAM permissions

### Health checks failing
- Ensure /health endpoint returns 200
- Check ALB health check path and port
- Verify container is listening on 0.0.0.0
- Review security group rules

### Database connection issues
- Verify RDS security group allows ECS tasks
- Check DATABASE_URL format
- Test connection from bastion host
- Review IAM database authentication

### High latency
- Enable CloudFront for edge caching
- Add RDS read replicas
- Scale ECS tasks horizontally
- Check Redis connection pooling

## Cost Optimization

### Use Spot Instances
Configure Fargate Spot for non-critical workloads (30% cheaper).

### Right-size Resources
Start with smaller instances and scale up based on metrics.

### Reserved Capacity
Purchase Reserved Instances for predictable baseline load.

### S3 Lifecycle Policies
Move old files to Glacier after 90 days to reduce storage costs.

### Monitor Unused Resources
Use AWS Cost Explorer to identify and remove idle resources.

## Security Hardening

- Enable VPC Flow Logs
- Use WAF with rate limiting rules
- Enable GuardDuty for threat detection
- Regular security audits with Security Hub
- Rotate secrets every 90 days
- Enable CloudTrail for API auditing
- Use least privilege IAM policies
- Enable encryption at rest and in transit everywhere