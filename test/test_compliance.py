
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.validators import validate_task_data, ValidationError

def test_compliance():
    # Test valid cases based on new Prompt requirements
    valid_cases = [
        {'title': 'Test1', 'task_type': '需求分析', 'sub_task_type': '市场需求分析'},
        {'title': 'Test2', 'task_type': '硬件设计', 'sub_task_type': '原型制作'},
        {'title': 'Test3', 'task_type': '软件开发', 'sub_task_type': '操作系统移植'},
        {'title': 'Test4', 'task_type': '系统集成', 'sub_task_type': '功耗优化'},
        {'title': 'Test5', 'task_type': '质量保证', 'sub_task_type': '安全认证'},
        {'title': 'Test6', 'task_type': '生产准备', 'sub_task_type': '供应链管理'},
    ]

    print("Testing Valid Cases...")
    for data in valid_cases:
        try:
            validate_task_data(data)
            print(f"PASS: {data['task_type']} - {data['sub_task_type']}")
        except ValidationError as e:
            print(f"FAIL: {data['task_type']} - {data['sub_task_type']} Error: {e.errors}")

    # Test invalid cases (old values that should now fail)
    invalid_cases = [
        {'title': 'Inv1', 'task_type': '固件开发', 'sub_task_type': 'Bootloader开发'}, # Old main type
        {'title': 'Inv2', 'task_type': '需求分析', 'sub_task_type': '功能需求定义'}, # Old sub type
        {'title': 'Inv3', 'task_type': '硬件设计', 'sub_task_type': 'EMC设计'}, # Old sub type
    ]

    print("\nTesting Invalid Cases (Should Fail)...")
    for data in invalid_cases:
        try:
            validate_task_data(data)
            print(f"FAIL: {data['task_type']} - {data['sub_task_type']} (Should have failed)")
        except ValidationError as e:
            print(f"PASS: {data['task_type']} - {data['sub_task_type']} Caught: {e.errors}")

if __name__ == "__main__":
    test_compliance()
