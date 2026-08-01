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
    // 立即清空输入框（乐观清空），避免等待流式生成期间输入框残留旧文本
    setValue("");
    await onSend(trimmed);
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
