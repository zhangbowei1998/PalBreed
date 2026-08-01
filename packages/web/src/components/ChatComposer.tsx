import { FormEvent, useState } from "react";

type Props = {
  loading: boolean;
  onSend: (text: string) => Promise<void>;
};

export function ChatComposer({ loading, onSend }: Props) {
  const [value, setValue] = useState("手工最高的是哪只帕鲁");

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
        placeholder="输入：手工最高 / 烧火最高 / 采矿最高…"
        disabled={loading}
      />
      <button type="submit" disabled={loading}>
        {loading ? "查询中..." : "发送"}
      </button>
    </form>
  );
}
