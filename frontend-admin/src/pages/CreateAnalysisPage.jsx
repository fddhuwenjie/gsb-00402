import { Form, Input, Select, Button, message, Spin, Divider, Upload } from 'antd'
import { ArrowLeftOutlined, ExperimentOutlined, UploadOutlined, InboxOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { signatureApi, analysisApi, baselineApi } from '../api/client'

const { Dragger } = Upload

const LANGUAGES = [
  { label: 'C', value: 'c' },
  { label: 'C++', value: 'c++' },
  { label: 'Python', value: 'python' },
  { label: 'Java', value: 'java' },
  { label: 'C#', value: 'c#' },
  { label: 'Rust', value: 'rust' },
  { label: 'Perl', value: 'perl' },
]

// 测试代码示例
const TEST_CODE = `// 测试代码 - 包含密码学函数调用
#include <stdio.h>

void test_crypto() {
    // mbedtls 函数
    mbedtls_ssl_init(NULL);
    mbedtls_ssl_handshake(NULL);
    mbedtls_aes_init(NULL);
    mbedtls_sha256_init(NULL);
    
    // OpenSSL 函数
    EVP_CIPHER_CTX_new();
    RSA_new();
    SHA256_Init(NULL);
}

int main() {
    test_crypto();
    return 0;
}
`

export default function CreateAnalysisPage() {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [sigFiles, setSigFiles] = useState([])
  const [sigLoading, setSigLoading] = useState(true)
  const [baselines, setBaselines] = useState([])
  const [fileList, setFileList] = useState([])

  useEffect(() => {
    Promise.all([
      signatureApi.list(1, 100).then((res) => setSigFiles(res.data.items)),
      baselineApi.list(1, 100).then((res) => setBaselines(res.data.items)).catch(() => {}),
    ]).finally(() => setSigLoading(false))
  }, [])

  const onFinish = async (values) => {
    if (fileList.length === 0) {
      message.error('请上传代码文件')
      return
    }
    if (!values.project_key || !values.project_key.trim()) {
      message.error('请输入项目标识')
      return
    }
    
    setLoading(true)
    try {
      // 使用 FormData 上传文件
      const formData = new FormData()
      formData.append('name', values.name)
      formData.append('language', values.language)
      formData.append('project_key', values.project_key.trim())
      formData.append('signature_file_ids', JSON.stringify(values.signature_file_ids))
      if (values.baseline_id) {
        formData.append('baseline_id', values.baseline_id)
      }
      
      // 添加所有文件
      fileList.forEach((file) => {
        formData.append('files', file.originFileObj || file)
      })
      
      const res = await analysisApi.createWithFiles(formData)
      message.success('分析任务创建成功')
      navigate(`/analyses/${res.data.task.id}`)
    } catch {
      // handled by interceptor
    } finally {
      setLoading(false)
    }
  }

  // 填充测试数据
  const fillTestData = () => {
    form.setFieldsValue({
      name: '测试分析任务 - MbedTLS扫描',
      language: 'c',
      signature_file_ids: sigFiles.length > 0 ? [sigFiles[0].id] : [],
    })
    
    // 创建测试文件
    const testFile = new File([TEST_CODE], 'test_crypto.c', { type: 'text/plain' })
    setFileList([{
      uid: '-1',
      name: 'test_crypto.c',
      status: 'done',
      originFileObj: testFile,
    }])
    
    message.info('已填充测试数据和测试代码文件')
  }

  const uploadProps = {
    multiple: true,
    fileList,
    beforeUpload: (file) => {
      // 不自动上传，手动控制
      return false
    },
    onChange: ({ fileList: newFileList }) => {
      setFileList(newFileList)
    },
    onRemove: (file) => {
      setFileList(fileList.filter(f => f.uid !== file.uid))
    },
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%', maxWidth: 640, marginBottom: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/analyses')}>返回</Button>
        <h2 style={{ margin: 0 }}>新建分析任务</h2>
      </div>

      <div style={{ background: 'white', borderRadius: 12, padding: 32, width: '100%', maxWidth: 640, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        {sigLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : (
          <Form form={form} layout="vertical" onFinish={onFinish} requiredMark="optional">
            <Form.Item name="name" label="任务名称" rules={[{ required: true, message: '请输入任务名称' }]}>
              <Input placeholder="例如：MbedTLS扫描 - 项目A" />
            </Form.Item>

            <Form.Item name="language" label="开发语言" rules={[{ required: true, message: '请选择语言' }]}>
              <Select options={LANGUAGES} placeholder="选择代码语言类型" />
            </Form.Item>

            <Form.Item
              name="project_key"
              label="项目标识"
              rules={[{ required: true, message: '请输入项目标识' }]}
              extra="用于标识同一代码项目，跨多次上传保持一致即可与基线对比。选择对比基线后将自动填充。"
            >
              <Input placeholder="例如：myapp-v2 或 /opt/projects/myapp" />
            </Form.Item>

            <Form.Item
              label="代码文件"
              required
              extra="支持上传单个或多个源代码文件（.c, .cpp, .py, .java 等）"
            >
              <Dragger {...uploadProps}>
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
                <p className="ant-upload-hint">支持单个或批量上传代码文件</p>
              </Dragger>
            </Form.Item>

            <Form.Item
              name="signature_file_ids"
              label="特征文件"
              rules={[{ required: true, message: '请选择至少一个特征文件' }]}
            >
              <Select
                mode="multiple"
                placeholder="选择一个或多个YARA特征文件"
                options={sigFiles.map((s) => ({
                  label: `${s.name} (${s.function_count} 函数)`,
                  value: s.id,
                }))}
              />
            </Form.Item>

            <Form.Item
              name="baseline_id"
              label="对比基线"
              extra="可选。选择基线后，分析完成将自动生成新增/移除/变化的密码资产差异报告"
            >
              <Select
                allowClear
                placeholder="不使用基线（仅做全新分析）"
                onChange={(val) => {
                  if (val) {
                    const b = baselines.find((x) => x.id === val)
                    if (b && b.project_key) {
                      form.setFieldsValue({ project_key: b.project_key })
                    }
                  }
                }}
                options={baselines.map((b) => ({
                  label: `${b.name} [${b.language?.toUpperCase()}] · ${b.asset_count} 资产`,
                  value: b.id,
                }))}
              />
            </Form.Item>

            <Form.Item>
              <Button type="primary" htmlType="submit" loading={loading} size="large" block>
                开始分析
              </Button>
            </Form.Item>

            <Divider style={{ margin: '16px 0' }}>快速测试</Divider>

            <Button 
              icon={<ExperimentOutlined />} 
              onClick={fillTestData} 
              block
              style={{ marginBottom: 8 }}
            >
              填充测试数据
            </Button>
            <p style={{ textAlign: 'center', color: '#999', fontSize: 12, margin: 0 }}>
              点击上方按钮自动填充测试数据和示例代码文件
            </p>
          </Form>
        )}
      </div>
    </div>
  )
}
