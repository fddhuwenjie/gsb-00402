import { Form, Input, Select, Button, message, Spin, Divider, Upload } from 'antd'
import { ArrowLeftOutlined, ExperimentOutlined, UploadOutlined, InboxOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { signatureApi, analysisApi } from '../api/client'

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
  const [fileList, setFileList] = useState([])

  useEffect(() => {
    signatureApi.list(1, 100)
      .then((res) => setSigFiles(res.data.items))
      .finally(() => setSigLoading(false))
  }, [])

  const onFinish = async (values) => {
    if (fileList.length === 0) {
      message.error('请上传代码文件')
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
      project_key: 'demo-project',
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
              extra="用于识别同一项目：对同一项目的多次上传请使用相同标识，才能与已有基线比较"
            >
              <Input placeholder="例如：my-service 或 project-a（同一项目需保持一致）" maxLength={255} />
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
