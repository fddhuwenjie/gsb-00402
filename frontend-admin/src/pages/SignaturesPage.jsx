import { Table, Button, Modal, Form, Input, Upload, message, Tooltip, Popconfirm } from 'antd'
import { UploadOutlined, PlusOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { signatureApi } from '../api/client'

export default function SignaturesPage() {
  const navigate = useNavigate()
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [form] = Form.useForm()
  const isAdmin = (() => {
    try { return JSON.parse(localStorage.getItem('user'))?.role === 'admin' } catch { return false }
  })()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await signatureApi.list(p)
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [page])

  const handleUpload = async (values) => {
    const { name, description, file } = values
    if (!file?.fileList?.[0]) {
      message.warning('Please select a YARA file')
      return
    }
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('name', name)
      formData.append('description', description || '')
      formData.append('file', file.fileList[0].originFileObj)
      await signatureApi.upload(formData)
      message.success('上传成功')
      setModalOpen(false)
      form.resetFields()
      fetchData(1)
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (id) => {
    await signatureApi.delete(id)
    message.success('删除成功')
    fetchData()
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60, fixed: 'left' },
    { title: '名称', dataIndex: 'name', width: 180, ellipsis: true },
    { title: '原始文件名', dataIndex: 'original_filename', width: 180, ellipsis: true },
    { title: '规则数', dataIndex: 'rule_count', width: 80, align: 'center' },
    { title: '函数数', dataIndex: 'function_count', width: 80, align: 'center' },
    {
      title: '创建时间', dataIndex: 'created_at', width: 180,
      render: (v) => <span style={{ whiteSpace: 'nowrap' }}>{dayjs(v).format('YYYY-MM-DD HH:mm:ss')}</span>,
    },
    {
      title: '操作', width: 100, align: 'center', fixed: 'right',
      render: (_, record) => (
        <span style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
          <Tooltip title="查看详情">
            <Button type="text" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/signatures/${record.id}`)} />
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
        <h2>特征文件管理</h2>
        {isAdmin && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            上传特征文件
          </Button>
        )}
      </div>

      <div style={{ background: 'white', borderRadius: 12, padding: 24, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Table
          dataSource={data}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 750 }}
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
        title="上传YARA特征文件"
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields() }}
        footer={null}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleUpload}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：MbedTLS函数特征" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="可选的描述信息" />
          </Form.Item>
          <Form.Item name="file" label="特征文件（.yar / .yara）" rules={[{ required: true, message: '请选择文件' }]}>
            <Upload beforeUpload={() => false} maxCount={1} accept=".yar,.yara">
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={uploading} block>
              上传
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
