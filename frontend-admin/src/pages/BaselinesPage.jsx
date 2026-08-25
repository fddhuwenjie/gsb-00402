import { Table, Button, Tag, Tooltip, Popconfirm, Modal, Form, Input, Select, message } from 'antd'
import { PlusOutlined, EyeOutlined, DeleteOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { baselineApi, analysisApi } from '../api/client'

export default function BaselinesPage() {
  const navigate = useNavigate()
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [completedTasks, setCompletedTasks] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()
  const isAdmin = (() => {
    try { return JSON.parse(localStorage.getItem('user'))?.role === 'admin' } catch { return false }
  })()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await baselineApi.list(p)
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [page])

  const openModal = async () => {
    setModalOpen(true)
    const res = await analysisApi.list(1, 100)
    setCompletedTasks((res.data.items || []).filter((t) => t.status === 'completed'))
  }

  const handleCreate = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      await baselineApi.create(values)
      message.success('基线保存成功')
      setModalOpen(false)
      form.resetFields()
      fetchData()
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id) => {
    await baselineApi.delete(id)
    message.success('删除成功')
    fetchData()
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 55, fixed: 'left' },
    { title: '基线名称', dataIndex: 'name', width: 180, ellipsis: true },
    { title: '来源分析', dataIndex: 'task_name', width: 180, ellipsis: true },
    {
      title: '语言', dataIndex: 'language', width: 70, align: 'center',
      render: (v) => <Tag color="blue">{v?.toUpperCase()}</Tag>,
    },
    { title: '代码路径', dataIndex: 'code_path', width: 200, ellipsis: true },
    { title: '资产数', dataIndex: 'asset_count', width: 80, align: 'center' },
    { title: '创建者', dataIndex: 'creator_name', width: 90 },
    {
      title: '创建时间', dataIndex: 'created_at', width: 180,
      render: (v) => <span style={{ whiteSpace: 'nowrap' }}>{dayjs(v).format('YYYY-MM-DD HH:mm:ss')}</span>,
    },
    {
      title: '操作', width: 100, align: 'center', fixed: 'right',
      render: (_, record) => (
        <span style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
          <Tooltip title="查看详情">
            <Button type="text" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/baselines/${record.id}`)} />
          </Tooltip>
          {isAdmin && (
            <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
              <Tooltip title="删除">
                <Button type="text" danger size="small" icon={<DeleteOutlined />} />
              </Tooltip>
            </Popconfirm>
          )}
        </span>
      ),
    },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>基线管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={openModal}>
          保存基线
        </Button>
      </div>

      <div style={{ background: 'white', borderRadius: 12, padding: 24, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Table
          dataSource={data}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1000 }}
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
        title="保存分析基线"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="基线名称" rules={[{ required: true, message: '请输入基线名称' }]}>
            <Input placeholder="例如：v1.0 发布基线" maxLength={200} />
          </Form.Item>
          <Form.Item name="task_id" label="来源分析任务" rules={[{ required: true, message: '请选择已完成的分析任务' }]}>
            <Select
              placeholder="选择已完成的分析任务"
              showSearch
              optionFilterProp="label"
              options={completedTasks.map((t) => ({
                value: t.id,
                label: `#${t.id} ${t.name} (${t.language?.toUpperCase()})`,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
