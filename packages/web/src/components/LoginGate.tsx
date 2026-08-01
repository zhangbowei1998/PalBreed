import { Button } from "antd";
import { LoginOutlined } from "@ant-design/icons";

type Props = {
  onLogin: () => void;
};

export function LoginGate({ onLogin }: Props) {
  return (
    <div className="login-gate">
      <div className="login-gate-card">
        <span className="login-gate-emoji" aria-hidden="true">🔒</span>
        <h2>登录后使用</h2>
        <p>帕鲁AI助手需要登录后才能使用，每个账号的记忆相互独立。</p>
        <Button
          type="primary"
          size="large"
          icon={<LoginOutlined />}
          onClick={onLogin}
        >
          登录 / 注册
        </Button>
      </div>
    </div>
  );
}
