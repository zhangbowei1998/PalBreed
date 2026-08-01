import type { ChatMessage } from "../types";

type Props = {
  messages: ChatMessage[];
};

export function MessageList({ messages }: Props) {
  return (
    <div className="message-list">
      {messages.map((msg) => (
        <article key={msg.id} className={`message message-${msg.role}`}>
          <header>{msg.role === "user" ? "你" : "Agent"}</header>
          <p>{msg.content}</p>
        </article>
      ))}
    </div>
  );
}
