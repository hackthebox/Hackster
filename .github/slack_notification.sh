#!/bin/bash

PROJECT="Hackster"
PROJECT_URL="https://github.com/hackthebox/hackster"

GITHUB_SHA_SHORT="$(echo "$GITHUB_SHA" | cut -c1-7)"

function send_request
{
    COLOR=$1
    MESSAGE=$2

    JSON_DATA=$(cat <<EOF
    {
        "text": "$MESSAGE",
        "attachments": [
            {
                "title": "Details",
                "color": "$COLOR",
                "fields": [
                    {
                        "title": "Project",
                        "value": "<$PROJECT_URL|$PROJECT>",
                        "short": true
                    },
                    {
                        "title": "Commit",
                        "value": "<$PROJECT_URL/commit/$GITHUB_SHA|$GITHUB_SHA_SHORT>",
                        "short": true
                    },
                    {
                        "title": "Committer",
                        "value": "$COMMITTER",
                        "short": true
                    },
                    {
                        "title": "Branch",
                        "value": "${GITHUB_REF##*/}",
                        "short": true
                    }
                ],
                "actions": [
                    {
                        "name": "view_action",
                        "text": "View Action",
                        "type": "button",
                        "url": "$PROJECT_URL/actions/runs/$GITHUB_RUN_ID?check_suite_focus=true"
                    }
                ]
            }
        ]
    }
EOF
)
    curl -H "Content-Type: application/json" "$SLACK_WEBHOOK_URL" --data "$JSON_DATA" > /dev/null 2>&1
}

case $1 in
    "failed")
        send_request "#a30300" "Your $PROJECT project has failed to deploy."
        ;;
    "deployed")
        send_request "#2eb886" "Your $PROJECT project has deployed successfully."
        ;;
    *)
        ;;
esac
