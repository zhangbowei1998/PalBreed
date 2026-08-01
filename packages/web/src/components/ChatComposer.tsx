import { FormEvent, useState } from "react";

type Props = {
  loading: boolean;
  onSend: (text: string) => Promise<void>;
};

export function ChatComposer({ loading, onSend }: Props) {
  const [value, setValue] = useState("手工等级最高的帕鲁怎么配种");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const text = value.trim();
    if (!text) return;
    await onSend(text);
    setValue("");
  }

  return (
    <form className="composer" onSubmit={submit}>
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="输入：手工等级最高的帕鲁怎么配种"
      />
      <button type="submit" disabled={loading}>
        发送
      </button>
    </form>
  );
}
