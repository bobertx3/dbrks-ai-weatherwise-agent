import { motion } from 'framer-motion';
import { memo } from 'react';
import type { UseChatHelpers } from '@ai-sdk/react';
import type { ChatMessage } from '@chat-template/core';
import { Suggestion } from './elements/suggestion';
import { softNavigateToChatId } from '@/lib/navigation';
import { useAppConfig } from '@/contexts/AppConfigContext';

interface FollowUpActionsProps {
  chatId: string;
  sendMessage: UseChatHelpers<ChatMessage>['sendMessage'];
  lastAssistantMessage: string;
}

function getFollowUps(lastMessage: string): string[] {
  const lower = lastMessage.toLowerCase();

  // Context-aware follow-ups based on what the agent just talked about
  if (lower.includes('at_risk') || lower.includes('borderline') || lower.includes('risk')) {
    return [
      'Pull supplier SOP escalation details for at-risk shipments',
      'Draft an alert email to the logistics team',
      'What backup inventory is available?',
    ];
  }

  if (lower.includes('shipment') || lower.includes('shp-')) {
    return [
      'Check weather conditions at the destination',
      'Show supplier contact details for these shipments',
      'Are there backup inventory options?',
    ];
  }

  if (lower.includes('supplier') || lower.includes('tier')) {
    return [
      'What shipments are in-transit from this supplier?',
      'Show escalation procedures from their SOP',
      'Check inventory at backup sites',
    ];
  }

  if (lower.includes('inventory') || lower.includes('backup')) {
    return [
      'Which shipments are currently delayed?',
      'Draft an email about rerouting options',
      'Check weather at the nearest distribution center',
    ];
  }

  if (lower.includes('email') || lower.includes('sent')) {
    return [
      'Send an SMS alert about this issue',
      'Check if there are other at-risk shipments',
      'Show me the full inventory overview',
    ];
  }

  // Default follow-ups
  return [
    'Check weather in New York — any shipments at risk?',
    'Show me all delayed shipments',
    'What backup inventory do we have?',
  ];
}

function PureFollowUpActions({
  chatId,
  sendMessage,
  lastAssistantMessage,
}: FollowUpActionsProps) {
  const { chatHistoryEnabled } = useAppConfig();
  const followUps = getFollowUps(lastAssistantMessage);

  return (
    <div className="flex flex-wrap gap-2 px-2">
      {followUps.map((suggestion, index) => (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 * index }}
          key={suggestion}
        >
          <Suggestion
            suggestion={suggestion}
            onClick={(s) => {
              softNavigateToChatId(chatId, chatHistoryEnabled);
              sendMessage({
                role: 'user',
                parts: [{ type: 'text', text: s }],
              });
            }}
            className="h-auto whitespace-normal px-3 py-1.5 text-left text-xs"
          >
            {suggestion}
          </Suggestion>
        </motion.div>
      ))}
    </div>
  );
}

export const FollowUpActions = memo(PureFollowUpActions);
