#!/bin/bash

# LLMOps Agent - Bedrock Agent Setup Script (Manual IAM Version)
# This script creates the Bedrock Agent assuming IAM role already exists

set -e

# Configuration
REGION="us-east-1"
ACCOUNT_ID="335995680325"
AGENT_NAME="llmops-orchestrator"
LAMBDA_ARN="arn:aws:lambda:us-east-1:335995680325:function:llmops-cier-runner"
AGENT_ROLE_NAME="llmops-bedrock-agent-role"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Bedrock Agent Setup for LLMOps Agent"
echo "=========================================="
echo ""

# Check if role exists
echo -e "${YELLOW}Checking IAM role...${NC}"
AGENT_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${AGENT_ROLE_NAME}"

if ! aws iam get-role --role-name ${AGENT_ROLE_NAME} --region ${REGION} &>/dev/null; then
    echo -e "${RED}❌ IAM role '${AGENT_ROLE_NAME}' does not exist.${NC}"
    echo ""
    echo "Please create the role manually with the following steps:"
    echo ""
    echo "1. Create trust policy file (bedrock-agent-trust-policy.json):"
    cat <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "335995680325"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:bedrock:us-east-1:335995680325:agent/*"
        }
      }
    }
  ]
}
EOF
    echo ""
    echo "2. Create the role:"
    echo "   aws iam create-role --role-name ${AGENT_ROLE_NAME} --assume-role-policy-document file://bedrock-agent-trust-policy.json"
    echo ""
    echo "3. Create permissions policy file (bedrock-agent-permissions.json):"
    cat <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:us-east-1:335995680325:function:llmops-cier-runner"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:335995680325:log-group:/aws/bedrock/agent/*"
    }
  ]
}
EOF
    echo ""
    echo "4. Attach the policy:"
    echo "   aws iam put-role-policy --role-name ${AGENT_ROLE_NAME} --policy-name BedrockAgentPermissions --policy-document file://bedrock-agent-permissions.json"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo -e "${GREEN}✓ IAM role exists: ${AGENT_ROLE_ARN}${NC}"

# Step 2: Read system prompt
echo -e "${YELLOW}Step 2: Preparing system prompt...${NC}"

INSTRUCTION=$(cat /home/sri-chakra/Documents/projects/llmops-agent/docs/artifacts/orchestrator-system-prompt.txt)

# Step 3: Create or get Bedrock Agent
echo -e "${YELLOW}Step 3: Creating or getting Bedrock Agent...${NC}"

# Try to create agent, if it exists, get its ID
AGENT_ID=$(aws bedrock-agent create-agent \
    --region ${REGION} \
    --agent-name ${AGENT_NAME} \
    --agent-resource-role-arn ${AGENT_ROLE_ARN} \
    --foundation-model "anthropic.claude-3-5-sonnet-20241022-v2:0" \
    --instruction "${INSTRUCTION}" \
    --description "MLOps orchestrator agent for autonomous model training" \
    --idle-session-ttl-in-seconds 600 \
    --query 'agent.agentId' \
    --output text 2>/dev/null || \
aws bedrock-agent list-agents \
    --region ${REGION} \
    --query "agentSummaries[?agentName=='${AGENT_NAME}'].agentId | [0]" \
    --output text)

echo -e "${GREEN}✓ Bedrock Agent ID: ${AGENT_ID}${NC}"

# Step 4: Create or get Action Group for Lambda (launch_training)
echo -e "${YELLOW}Step 4: Creating or getting action group for Lambda tool...${NC}"

cat > /tmp/lambda-action-group-schema.json <<EOF
{
  "openapi": "3.0.0",
  "info": {
    "title": "Training Launch Tool",
    "version": "1.0.0",
    "description": "Launches SageMaker training jobs"
  },
  "paths": {
    "/launch-training": {
      "post": {
        "summary": "Launch a training job",
        "description": "Starts a SageMaker training job for the ciER dataset",
        "operationId": "launchTraining",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "session_id": {
                    "type": "string",
                    "description": "Session ID for tracking"
                  }
                },
                "required": ["session_id"]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Training job started successfully",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "success": {
                      "type": "boolean"
                    },
                    "job_id": {
                      "type": "string"
                    },
                    "sagemaker_job_name": {
                      "type": "string"
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
EOF

# Create or get action group for Lambda
# The payload must be a string, so we stringify the JSON
SCHEMA_PAYLOAD=$(cat /tmp/lambda-action-group-schema.json | jq -c . | jq -Rs .)

# Try to create, if it exists, get the ID
ACTION_GROUP_ID_LAMBDA=$(aws bedrock-agent create-agent-action-group \
    --region ${REGION} \
    --agent-id ${AGENT_ID} \
    --agent-version DRAFT \
    --action-group-name "launch-training-tool" \
    --action-group-executor "{\"lambda\":\"${LAMBDA_ARN}\"}" \
    --api-schema "{\"payload\":${SCHEMA_PAYLOAD}}" \
    --description "Launches SageMaker training jobs" \
    --query 'agentActionGroup.actionGroupId' \
    --output text 2>/dev/null || \
aws bedrock-agent list-agent-action-groups \
    --region ${REGION} \
    --agent-id ${AGENT_ID} \
    --agent-version DRAFT \
    --query "actionGroupSummaries[?actionGroupName=='launch-training-tool'].actionGroupId | [0]" \
    --output text)

echo -e "${GREEN}✓ Lambda action group ID: ${ACTION_GROUP_ID_LAMBDA}${NC}"

# Step 5: Prepare the agent
echo -e "${YELLOW}Step 5: Preparing agent...${NC}"

aws bedrock-agent prepare-agent \
    --region ${REGION} \
    --agent-id ${AGENT_ID} \
    --query 'agentStatus' \
    --output text

# Wait for agent to be prepared
echo "Waiting for agent to be prepared..."
MAX_WAIT=60  # 60 seconds
WAIT_TIME=0
while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    AGENT_STATUS=$(aws bedrock-agent get-agent \
        --region ${REGION} \
        --agent-id ${AGENT_ID} \
        --query 'agent.agentStatus' \
        --output text)

    if [ "$AGENT_STATUS" = "PREPARED" ] || [ "$AGENT_STATUS" = "NOT_PREPARED" ]; then
        echo -e "${GREEN}✓ Agent status: ${AGENT_STATUS}${NC}"
        break
    fi

    echo "  Agent status: ${AGENT_STATUS}, waiting..."
    sleep 5
    WAIT_TIME=$((WAIT_TIME + 5))
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}⚠ Agent is still preparing. This is normal.${NC}"
    echo -e "${YELLOW}⚠ You may need to wait a few more seconds before creating the alias manually.${NC}"
fi

# Step 6: Create or get Agent Alias
echo -e "${YELLOW}Step 6: Creating or getting agent alias...${NC}"

# Try to create alias, if it exists or agent is still preparing, get existing alias
ALIAS_ID=$(aws bedrock-agent create-agent-alias \
    --region ${REGION} \
    --agent-id ${AGENT_ID} \
    --agent-alias-name "v1" \
    --description "Version 1 alias for LLMOps agent" \
    --query 'agentAlias.agentAliasId' \
    --output text 2>/dev/null || \
aws bedrock-agent list-agent-aliases \
    --region ${REGION} \
    --agent-id ${AGENT_ID} \
    --query "agentAliasSummaries[?agentAliasName=='v1'].agentAliasId | [0]" \
    --output text)

echo -e "${GREEN}✓ Agent alias ID: ${ALIAS_ID}${NC}"

# Step 7: Add Lambda permissions
echo -e "${YELLOW}Step 7: Granting Bedrock permission to invoke Lambda...${NC}"

aws lambda add-permission \
    --function-name llmops-cier-runner \
    --statement-id bedrock-agent-invoke \
    --action lambda:InvokeFunction \
    --principal bedrock.amazonaws.com \
    --source-arn "arn:aws:bedrock:${REGION}:${ACCOUNT_ID}:agent/${AGENT_ID}" \
    2>/dev/null || echo "Permission already exists"

echo -e "${GREEN}✓ Lambda permissions granted${NC}"

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}Bedrock Agent Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Agent Details:"
echo "  Agent ID: ${AGENT_ID}"
echo "  Alias ID: ${ALIAS_ID}"
echo "  Agent ARN: arn:aws:bedrock:${REGION}:${ACCOUNT_ID}:agent/${AGENT_ID}"
echo "  Alias ARN: arn:aws:bedrock:${REGION}:${ACCOUNT_ID}:agent-alias/${AGENT_ID}/${ALIAS_ID}"
echo ""
echo "Action Groups:"
echo "  - launch-training-tool (Lambda): ${LAMBDA_ARN}"
echo ""
echo "Update your .env file with:"
echo ""
echo "BEDROCK_AGENT_ID=${AGENT_ID}"
echo "BEDROCK_AGENT_ALIAS_ID=${ALIAS_ID}"
echo ""
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Update .env with the values above"
echo "2. Test the agent with: poetry run python scripts/test_bedrock_agent.py"
echo "3. Start the FastAPI server: poetry run uvicorn llmops_agent.api.main:app --reload"
echo ""
