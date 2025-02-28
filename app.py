import sys
import os
import shutil
import h5py
import numpy as np
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.gp import gp_Vec, gp_Trsf
from OCC.Core.TopLoc import TopLoc_Location
from starlette.responses import FileResponse

# # 为引入cadlib模块需添加索引路径。添加路径后，引入不需要写路径的根名。例如cad/cadlib/curves，只需要import cadlib.curves
deepcad_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../cad'))
sys.path.append(deepcad_path)
print(sys.path)

from cadlib.visualize import vec2CADsolid
from cadlib.extrude import CADSequence
from single_encode_decode import *
from config.configAE import *
from trainer.trainerAE import *

app = FastAPI()
fetchIP = "http://116.172.93.35:8000"

# 配置 CORS
origins = [
    "http://localhost",
    "http://127.0.0.1",
    fetchIP,
    "http://127.0.0.1:8000"
    "http://127.0.0.1:1234"
    "http://0.0.0.0:1234"
    "http://0.0.0.0:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 允许哪些来源的请求
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

# 返回信息
class ResponseMessage(BaseModel):
    message: str
    stl_file_url: str


# 检查形状有效性
def check_shape_validity(shape):
    analyzer = BRepCheck_Analyzer(shape)
    if not analyzer.IsValid():
        return False
    return True


# 导出STL文件
def export_shape_to_stl(shape, filename, deflection=0.1):
    # stl文件路径，默认与上传的h5同路径
    stl_dir = os.path.dirname(filename)
    if not os.path.exists(stl_dir):
        os.makedirs(stl_dir)
    check_shape_validity(shape)
    mesh = BRepMesh_IncrementalMesh(shape, deflection)
    mesh.Perform()
    if not mesh.IsDone():
        return False
    writer = StlAPI_Writer()
    try:
        result = writer.Write(shape, filename)
        if result:
            return True
        return False
    except Exception as e:
        return False


# 处理 H5 文件并导出 STL
def process_h5_file(src, deflection):
    try:
        with h5py.File(src.file, 'r') as fp:
            out_vec = fp["out_vec"][:].astype(np.float)
            out_shape = vec2CADsolid(out_vec)
            # STL 文件名创建，使用上传文件名生成 STL 文件
            stl_filename = os.path.splitext(src.filename)[0] + ".stl"
            stl_path = os.path.join("stl_files", stl_filename)  # 保存在 stl_files 目录下
            if export_shape_to_stl(out_shape, stl_path, deflection):
                return stl_path
            else:
                return None
    except Exception as e:
        print(f"Error processing H5 file: {e}")
        return None


# 导出stl接口
@app.post("/export_stl/", response_model=ResponseMessage)
async def export_stl(
    src: UploadFile = File(...),
    file_format: str = Form(...),  # 直接接收
    deflection: float = Form(...)    # 直接接收
):
    # 保存上传的文件
    upload_dir = "uploaded_files"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    src_path = os.path.join(upload_dir, src.filename)

    # 保存文件到本地
    with open(src_path, "wb") as f:
        shutil.copyfileobj(src.file, f)

    # 检查文件类型并处理
    if file_format == "h5" and src.filename.endswith(".h5"):
        stl_file_path = process_h5_file(src, deflection)
        if stl_file_path:
            # 生成的 STL 文件 URL
            stl_file_url = f"{fetchIP}/download/{os.path.basename(stl_file_path)}"
            return ResponseMessage(
                message=f"STL file successfully saved as: {stl_file_path}",
                stl_file_url=stl_file_url
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to process H5 file.")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format or file type.")


# 提供 STL 文件下载
@app.get("/download/{stl_filename}")
async def download_stl(stl_filename: str):
    stl_file_path = os.path.join("stl_files", stl_filename)
    if os.path.exists(stl_file_path):
        return FileResponse(stl_file_path, media_type='application/stl')
    else:
        raise HTTPException(status_code=404, detail="STL file not found.")


# 整合功能，提供outh5来转化为stl文件，可视化是前端功能
@app.post("/h5_to_vis/", response_model=ResponseMessage)
async def h5_to_vis(
    src: UploadFile = File(...),
    file_format: str = Form(...),
    deflection: float = Form(...)
):
    # 保存上传的 H5 文件
    upload_dir = "uploaded_files"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    src_path = os.path.join(upload_dir, src.filename)

    with open(src_path, "wb") as f:
        shutil.copyfileobj(src.file, f)

    # 处理 H5 文件并导出 STL
    if file_format == "h5" and src.filename.endswith(".h5"):
        stl_file_path = process_h5_file(src, deflection)
        if stl_file_path:
            # 生成的 STL 文件 URL
            stl_file_url = f"{fetchIP}/download/{os.path.basename(stl_file_path)}"
            return ResponseMessage(
                message=f"STL file successfully saved as: {stl_file_path}",
                stl_file_url=stl_file_url
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to process H5 file.")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format or file type.")

# 编码
@app.post("/encode_h5/", response_model=ResponseMessage)
async def encode_h5(
    src: UploadFile = File(...),
    file_format: str = Form(...)
):
    """
    接收原始 h5 文件进行编码，输出 zs.h5 文件
    """
    # 保存上传的原始 H5 文件
    upload_dir = "uploaded_files"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    src_path = os.path.join(upload_dir, src.filename)

    with open(src_path, "wb") as f:
        shutil.copyfileobj(src.file, f)

    # 检查文件格式
    if file_format == "h5" and src.filename.endswith(".h5"):
        try:
            output_path = process_single_file(src_path, 'encode')
            # 保存编码后的 zs.h5 文件到 zs_h5_files 文件夹
            zs_output_dir = "zs_h5_files"
            if not os.path.exists(zs_output_dir):
                os.makedirs(zs_output_dir)
            final_output_path = os.path.join(zs_output_dir, os.path.basename(output_path))

            # 移动文件到 zs_h5_files 文件夹
            shutil.move(output_path, final_output_path)

            # 返回生成的 zs.h5 文件的 URL
            zs_file_url = f"{fetchIP}/download/{os.path.basename(final_output_path)}"
            return ResponseMessage(
                message=f"Encoded zs.h5 file saved as: {final_output_path}",
                stl_file_url=zs_file_url
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error during encoding: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format or file type.")


# 解码
@app.post("/decode_h5/", response_model=ResponseMessage)
async def decode_h5(
    src: UploadFile = File(...),
    file_format: str = Form(...)
):
    """
    接收编码后的 zs.h5 文件进行解码，输出 out.h5 文件
    """
    # 保存上传的 zs.h5 文件
    upload_dir = "uploaded_files"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    src_path = os.path.join(upload_dir, src.filename)

    with open(src_path, "wb") as f:
        shutil.copyfileobj(src.file, f)

    # 检查文件格式
    if file_format == "h5" and src.filename.endswith("_zs.h5"):
        try:
            # 执行解码操作
            output_path = process_single_file(src_path, 'decode')
            # 保存解码后的 out.h5 文件到 out_h5_files 文件夹
            out_output_dir = "out_h5_files"
            if not os.path.exists(out_output_dir):
                os.makedirs(out_output_dir)
            final_output_path = os.path.join(out_output_dir, os.path.basename(output_path))

            # 移动文件到 out_h5_files 文件夹
            shutil.move(output_path, final_output_path)

            # 返回生成的 out.h5 文件的 URL
            out_file_url = f"{fetchIP}/download/{os.path.basename(final_output_path)}"
            return ResponseMessage(
                message=f"Decoded out.h5 file saved as: {final_output_path}",
                stl_file_url=out_file_url
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error during decoding: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format or file type.")

# 综合编解码
@app.post("/encode_decode_h5/", response_model=ResponseMessage)
async def encode_decode_h5(
    src: UploadFile = File(...),
    file_format: str = Form(...),
    deflection: float = Form(...)
):
    """
    结合完整过程，接收原始 h5 文件，完成编码解码的过程，输出 out.h5 文件
    """
    # 保存上传的原始 H5 文件
    upload_dir = "uploaded_files"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    src_path = os.path.join(upload_dir, src.filename)

    with open(src_path, "wb") as f:
        shutil.copyfileobj(src.file, f)

    # 检查文件格式
    if file_format == "h5" and src.filename.endswith(".h5"):
        try:
            # 执行编码
            zs_output_path = process_single_file(src_path, 'encode')
            zs_output_dir = "zs_h5_files"
            if not os.path.exists(zs_output_dir):
                os.makedirs(zs_output_dir)
            zs_final_path = os.path.join(zs_output_dir, os.path.basename(zs_output_path))

            # 执行解码
            out_output_path = process_single_file(src_path, 'decode')
            out_output_dir = "out_h5_files"
            if not os.path.exists(out_output_dir):
                os.makedirs(out_output_dir)
            out_final_path = os.path.join(out_output_dir, os.path.basename(out_output_path))

            # 移动解码后的文件到 out_h5_files 文件夹
            shutil.move(out_output_path, out_final_path)

            # 返回生成的 out.h5 文件的 URL
            out_file_url = f"{fetchIP}/download/{os.path.basename(out_final_path)}"
            return ResponseMessage(
                message=f"Encoded and decoded out.h5 file saved as: {out_final_path}",
                stl_file_url=out_file_url
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error during encoding/decoding: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format or file type.")


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)