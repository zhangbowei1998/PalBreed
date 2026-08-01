import { Sender } from "@ant-design/x";
import { useState } from "react";

type Props = {
  loading: boolean;
  onSend: (text: string) => Promise<void>;
};

export function ChatComposer({ loading, onSend }: Props) {
  const [value, setValue] = useState("");

  async function handleSubmit(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    await onSend(trimmed);
    setValue("");
  }

  return (
    <Sender
      className="composer"
      value={value}
      onChange={setValue}
      onSubmit={handleSubmit}
      loading={loading}
      placeholder="问我：手工最高 / 烧火最高 / 阿努比斯怎么配种…"
      autoSize={{ minRows: 1, maxRows: 4 }}
    />
  );
}
