import { Form, Input, Modal, Tabs, App } from "antd";
import { useState } from "react";
import type { AuthUser } from "../hooks/useAuth";

type Props = {
  open: boolean;
  onClose: () => void;
  onLogin: (username: string, password: string) => Promise<AuthUser>;
  onRegister: (
    username: string,
    password: string,
    inviteCode: string
  ) => Promise<AuthUser>;
};

type AuthForm = { username: string; password: string; inviteCode: string };

const USERNAME_RULES = [
  { required: true, message: "请输入用户名" },
  { min: 3, max: 32, message: "用户名长度 3-32 位" },
  { pattern: /^[a-zA-Z0-9_\-\u4e00-\u9fa5]+$/, message: "仅限中英文、数字、_ 和 -" },
];
const PASSWORD_RULES = [
  { required: true, message: "请输入密码" },
  { min: 6, max: 64, message: "密码长度 6-64 位" },
];
const INVITE_RULES = [
  { required: true, message: "请输入邀请码" },
  { min: 4, max: 32, message: "邀请码长度 4-32 位" },
];

export function AuthModal({ open, onClose, onLogin, onRegister }: Props) {
  const { message } = App.useApp();
  const [tab, setTab] = useState("login");
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<AuthForm>();

  async function handleSubmit(values: AuthForm) {
    setSubmitting(true);
    try {
      if (tab === "login") {
        await onLogin(values.username, values.password);
        message.success("登录成功");
      } else {
        await onRegister(values.username, values.password, values.inviteCode);
        message.success("注册成功，已自动登录");
      }
      onClose();
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      title={tab === "login" ? "登录" : "注册"}
      okText={tab === "login" ? "登录" : "注册"}
      cancelText="取消"
      confirmLoading={submitting}
      onOk={() => form.submit()}
      onCancel={onClose}
      destroyOnHidden
      width={380}
    >
      <Tabs
        activeKey={tab}
        onChange={setTab}
        centered
        items={[
          { key: "login", label: "登录" },
          { key: "register", label: "注册" },
        ]}
      />
      <Form<AuthForm> form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item name="username" label="用户名" rules={USERNAME_RULES}>
          <Input placeholder="输入用户名" autoComplete="username" />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={PASSWORD_RULES}>
          <Input.Password placeholder="输入密码" autoComplete="current-password" />
        </Form.Item>
        {tab === "register" && (
          <Form.Item name="inviteCode" label="邀请码" rules={INVITE_RULES}>
            <Input placeholder="输入邀请码（需向管理员获取）" autoComplete="off" />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}
