#!/bin/bash

# LLMOps Agent - Bedrock Agent Setup Script
# This script creates the Bedrock Agent with action groups

set -e

# Configuration
REGION="us-east-1"
ACCOUNT_ID="335995680325"
AGENT_NAME="llmops-orchestrator"
LAMBDA_ARN="arn:aws:lambda:us-east-1:335995680325:function:llmops-cier-runner"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Bedrock Agent Setup for LLMOps Agent"
echo "=========================================="
echo ""

# Step 1: Create IAM Role for Bedrock Agent
echo -e "${YELLOW}Step 1: Creating IAM role for Bedrock Agent...${NC}"

# Trust policy for Bedrock Agent
cat > /tmp/bedrock-agent-trust-policy.json <<EOF
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
          "aws:SourceAccount": "${ACCOUNT_ID}"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:bedrock:${REGION}:${ACCOUNT_ID}:agent/*"
        }
      }
    }
  ]
}
EOF

# Create the role
aws iam create-role \
    --role-name llmops-bedrock-agent-role \
    --assume-role-policy-document file:///tmp/bedrock-agent-trust-policy.json \
    --description "Role for LLMOps Bedrock Agent" \
    2>/dev/null || echo "Role already exists"

# Permissions policy for Bedrock Agent
cat > /tmp/bedrock-agent-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": [
        "arn:aws:bedrock:${REGION}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "${LAMBDA_ARN}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/bedrock/agent/*"
    }
  ]
}
EOF

# Attach inline policy
aws iam put-role-policy \
    --role-name llmops-bedrock-agent-role \
    --policy-name BedrockAgentPermissions \
    --policy-document file:///tmp/bedrock-agent-permissions.json

echo -e "${GREEN}✓ IAM role created: llmops-bedrock-agent-role${NC}"

# Wait for role to propagate
echo "Waiting for IAM role to propagate..."
sleep 10

AGENT_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/llmops-bedrock-agent-role"

# Step 2: Read system prompt
echo -e "${YELLOW}Step 2: Preparing system prompt...${NC}"

INSTRUCTION=$(cat /home/sri-chakra/Documents/projects/llmops-agent/docs/artifacts/orchestrator-system-prompt.txt)

# Step 3: Create Bedrock Agent
echo -e "${YELLOW}Step 3: Creating Bedrock Agent...${NC}"

AGENT_ID=$(aws bedrock-agent create-agent \
    --region ${REGION} \
    --agent-name ${AGENT_NAME} \
    --agent-resource-role-arn ${AGENT_ROLE_ARN} \
    --foundation-model "anthropic.claude-3-5-sonnet-20241022-v2:0" \
    --instruction "${INSTRUCTION}" \
    --description "MLOps orchestrator agent for autonomous model training" \
    --idle-session-ttl-in-seconds 600 \
    --query 'agent.agentId' \
    --output text)

echo -e "${GREEN}✓ Bedrock Agent created: ${AGENT_ID}${NC}"

# Step 4: Create Action Group for Lambda (launch_training)
echo -e "${YELLOW}Step 4: Creating action group for Lambda tool...${NC}"

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

# Create action group for Lambda
ACTION_GROUP_ID_LAMBDA=$(aws bedrock-agent create-agent-action-group \
    --region ${REGION} \
    --agent-id ${AGENT_ID} \
    --agent-version DRAFT \
    --action-group-name "launch-training-tool" \
    --action-group-executor lambda="${LAMBDA_ARN}" \
    --api-schema file:///tmp/lambda-action-group-schema.json \
    --description "Launches SageMaker training jobs" \
    --query 'agentActionGroup.actionGroupId' \
    --output text)

echo -e "${GREEN}✓ Lambda action group created: ${ACTION_GROUP_ID_LAMBDA}${NC}"

# Step 5: Create Action Group for API (model selection, job status)
echo -e "${YELLOW}Step 5: Creating action group for API tools...${NC}"

cat > /tmp/api-action-group-schema.json <<EOF
{
  "openapi": "3.0.0",
  "info": {
    "title": "LLMOps Agent Tools API",
    "version": "1.0.0",
    "description": "API tools for model selection and job monitoring"
  },
  "servers": [
    {
      "url": "http://localhost:8000"
    }
  ],
  "paths": {
    "/api/tools/select-model": {
      "post": {
        "summary": "Select optimal model",
        "description": "Selects the best model based on constraints",
        "operationId": "selectModel",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "task_type": {
                    "type": "string",
                    "description": "ML task type (e.g., token-classification)"
                  },
                  "budget_usd": {
                    "type": "number",
                    "description": "Maximum budget in USD"
                  },
                  "max_time_hours": {
                    "type": "number",
                    "description": "Maximum training time in hours"
                  },
                  "min_f1": {
                    "type": "number",
                    "description": "Minimum F1 score required"
                  },
                  "session_id": {
                    "type": "string"
                  }
                },
                "required": ["task_type", "budget_usd"]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Model selected successfully",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "success": {
                      "type": "boolean"
                    },
                    "model_id": {
                      "type": "string"
                    },
                    "estimated_cost": {
                      "type": "number"
                    },
                    "estimated_time_hours": {
                      "type": "number"
                    },
                    "expected_f1": {
                      "type": "number"
                    }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/api/tools/get-job-status": {
      "post": {
        "summary": "Get job status",
        "description": "Retrieves the status of a training job",
        "operationId": "getJobStatus",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "job_id": {
                    "type": "string",
                    "description": "Training job ID"
                  }
                },
                "required": ["job_id"]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Job status retrieved successfully",
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
                    "status": {
                      "type": "string"
                    },
                    "progress": {
                      "type": "integer"
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

echo -e "${YELLOW}Note: API action group requires your FastAPI server to be publicly accessible.${NC}"
echo -e "${YELLOW}For hackathon, we'll use Lambda primarily. You can add API tools later.${NC}"

# For now, skip API action group (requires public endpoint)
# We'll use Lambda for all tools initially

# Step 6: Prepare the agent
echo -e "${YELLOW}Step 6: Preparing agent...${NC}"

aws bedrock-agent prepare-agent \
    --region ${REGION} \
    --agent-id ${AGENT_ID} \
    --query 'agentStatus'

echo -e "${GREEN}✓ Agent prepared${NC}"

# Step 7: Create Agent Alias
echo -e "${YELLOW}Step 7: Creating agent alias...${NC}"

ALIAS_ID=$(aws bedrock-agent create-agent-alias \
    --region ${REGION} \
    --agent-id ${AGENT_ID} \
    --agent-alias-name "v1" \
    --description "Version 1 alias for LLMOps agent" \
    --query 'agentAlias.agentAliasId' \
    --output text)

echo -e "${GREEN}✓ Agent alias created: ${ALIAS_ID}${NC}"

# Step 8: Add Lambda permissions
echo -e "${YELLOW}Step 8: Granting Bedrock permission to invoke Lambda...${NC}"

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
