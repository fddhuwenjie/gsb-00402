import { Table, Button, Modal, Form, Input, Select, Tag, Space, Popconfirm, message } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, CrownOutlined, UserOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import dayjs from 'dayjs'
import { userApi } from '../api/client'

export default function UsersPage() {
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()

  const currentUser = (() => {
    try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
  })()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await userApi.list(p)
      setData(res.data.items)
      setTotal(res.data.total)
    } catch {
      // handled by interceptor
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [page])

  const handleCreate = async (values) => {
    setSubmitting(true)
    try {
      await userApi.create(values)
      message.success('User created')
      setCreateOpen(false)
      createForm.resetFields()
      fetchData(1)
    } finally {
      setSubmitting(false)
    }
  }

  const handleEdit = (record) => {
    setEditingUser(record)
    editForm.setFieldsValue({ role: record.role, password: '' })
    setEditOpen(true)
  }

  const handleUpdate = async (values) => {
    setSubmitting(true)
    try {
      const payload = {}
      if (values.role !== editingUser.role) payload.role = values.role
      if (values.password?.trim()) payload.password = values.password
      if (Object.keys(payload).length === 0) {
        message.info('No changes')
        setEditOpen(false)
        return
      }
      await userApi.update(editingUser.id, payload)
      message.success('Updated')
      setEditOpen(false)
      fetchData()
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await userApi.delete(id)
      message.success('Deleted')
      fetchData()
    } catch {
      // handled by interceptor
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '用户名', dataIndex: 'username',
      render: (v, record) => (
        <Space>
          {record.role === 'admin'
            ? <CrownOutlined style={{ color: '#722ed1' }} />
            : <UserOutlined style={{ color: '#999' }} />}
          <span style={{ fontWeight: 500 }}>{v}</span>
        </Space>
      ),
    },
    {
      title: '角色', dataIndex: 'role', width: 120, align: 'center',
      render: (v) => v === 'admin'
        ? <Tag color="purple">管理员</Tag>
        : <Tag color="default">普通用户</Tag>,
    },
    {
      title: '创建时间', dataIndex: 'created_at', width: 180,
      render: (v) => <span style={{ whiteSpace: 'nowrap' }}>{dayjs(v).format('YYYY-MM-DD HH:mm:ss')}</span>,
    },
    {
      title: '操作', width: 150, align: 'center',
      render: (_, record) => (
        <Space size={0}>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          {record.id !== currentUser?.id && record.username !== 'admin' && (
            <Popconfirm title={`确定删除用户 ${record.username}？`} onConfirm={() => handleDelete(record.id)}>
              <Button type="link" danger size="small" icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>用户管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          创建用户
        </Button>
      </div>

      <div style={{ background: 'white', borderRadius: 12, padding: 24, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Table
          dataSource={data}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            onChange: setPage,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </div>

      <Modal
        title="创建用户"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); createForm.resetFields() }}
        footer={null}
        destroyOnClose
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }, { min: 3, message: '至少3个字符' }]}>
            <Input placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }, { min: 6, message: '至少6个字符' }]}>
            <Input.Password placeholder="密码" />
          </Form.Item>
          <Form.Item name="role" label="角色" initialValue="user">
            <Select options={[{ label: '普通用户', value: 'user' }, { label: '管理员', value: 'admin' }]} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>创建</Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`编辑用户: ${editingUser?.username}`}
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" onFinish={handleUpdate}>
          <Form.Item name="role" label="角色">
            <Select options={[{ label: '普通用户', value: 'user' }, { label: '管理员', value: 'admin' }]} />
          </Form.Item>
          <Form.Item name="password" label="新密码（留空不修改）">
            <Input.Password placeholder="留空则不修改密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>保存</Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
