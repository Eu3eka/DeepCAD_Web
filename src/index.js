import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

let scene, camera, renderer, controls;
let mesh;
let edges;

// 场景
function init() {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);

    // 获取可视化容器
    const visualizationContainer = document.getElementById('visualization');

    // 创建渲染器并设置大小
    renderer = new THREE.WebGLRenderer();
    renderer.setSize(visualizationContainer.clientWidth, visualizationContainer.clientHeight);
    
    // 将渲染器的 canvas 添加到可视化区域
    visualizationContainer.appendChild(renderer.domElement);

    scene.background = new THREE.Color(0xffffff);    // 背景色为白色

    const light = new THREE.AmbientLight(0x404040, 2);  // 环境光源, 强度为2
    scene.add(light);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 3); // 定向光源
    directionalLight.position.set(5, 5, 5).normalize();
    scene.add(directionalLight);

    camera.position.z = 5;

    // 初始化 OrbitControls
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; // 启用阻尼效果
    controls.dampingFactor = 0.25; // 设置阻尼效果的强度
    controls.screenSpacePanning = false; // 禁用平面移动

    // h5转stl
    // 顺序：点击button->触发第二行绑定的监听器，它会触发click弹出选文件框的效果->选择文件->change触发第一行的监听器
    // 所以，第一行的监听器应该绑定到input上，第二行的绑定到button上。
    document.getElementById('h5tostl-input').addEventListener('change',h5ToStl, false);// change表示用户选择文件后触发操作
    document.getElementById('h5-to-stl-button').addEventListener('click', function () {
        document.getElementById('h5tostl-input').click(); 
    });

    // 可视化stl
    document.getElementById('stlvis-input').addEventListener('change',stlToVis, false);
    document.getElementById('stl-upload-button').addEventListener('click', function () {
        document.getElementById('stlvis-input').click(); 
    });


    // 直接可视化h5
    document.getElementById('h5vis-input').addEventListener('change', h5ToVis, false);
    document.getElementById('h5-to-vis-button').addEventListener('click', () => {
        document.getElementById('h5vis-input').click();
    });    


}

// 直接可视化h5
async function h5ToVis (event){
    const file = event.target.files[0];
    if (!file) {
        console.error("No file selected.");
        return;
    }

    const formData = new FormData();
    formData.append("src", file);
    formData.append("file_format", "h5");
    formData.append("deflection", 0.1);

    try {
        // 向后端发送请求上传文件
        const response = await fetch("http://127.0.0.1:8000/h5_to_vis/", {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (response.ok && data.stl_file_url) {
            const stlFileUrl = data.stl_file_url;
            const stlFile = await fetchSTLFile(stlFileUrl);
            console.log("[h5ToVis] stlFileUrl" + stlFileUrl + "; stlFile:" + stlFile);
            stlToVis(stlFile);
        } else {
            throw new Error("Failed to convert H5 to STL.");
        }
    } catch (error) {
        console.error("Error uploading H5 file:", error);
    }
}

async function fetchSTLFile(stlFileUrl) {
    try {
        const response = await fetch(stlFileUrl);//这里fetch
        if (!response.ok) {
            throw new Error("Failed to fetch STL file.");
        }
        const contentType = response.headers.get('Content-Type');
        console.log('Content-Type:', contentType);

        if (!contentType || !contentType.includes('application/stl')) {
            throw new Error("Invalid STL file. Expected 'application/stl', but got: " + contentType);
        }
        const fileBlob = await response.blob(); 
        console.log('[fetchSTL]:'+fileBlob);
        return fileBlob; 
    } catch (error) {
        console.error("Error fetching STL file:", error);
        throw error;
    }
}



//将h5转为stl文件
async function h5ToStl(event) {
    const file = event.target.files[0]; // 从事件中获取文件对象

    if (!file) {
        console.error('No file selected');
        return;
    }
    const formData = new FormData();
    formData.append("src", file); 
    formData.append("file_format", "h5");
    formData.append("deflection", 0.1);  

    for (const [key, value] of formData.entries()) {
        console.log(`${key}: ${value}`);
    }

    return fetch('http://127.0.0.1:8000/export_stl/', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => { // 后端返回的是stl存储的路径
        if (data && data.stl_file_url) {
            const stlFileUrl = data.stl_file_url; 
            createDownloadButton(stlFileUrl);
        } else {
            throw new Error('STL file generation failed');
        }
    })
    .catch(error => {
        console.error('Error exporting STL:', error);
        throw error;
    });
}

// 用于下载stl的下载按钮
function createDownloadButton(stlFileUrl) {
    // 获取已经创建的div
    const downloadContainer = document.querySelector('.button-container-download');

    const downloadButton = document.createElement('a');
    downloadButton.href = stlFileUrl;
    downloadButton.download = stlFileUrl.split('/').pop();  // 获取文件名作为下载文件名
    downloadButton.textContent = "点击保存生成的STL文件";
   
    downloadButton.classList.add('button');  // 添加 'button' 样式类

    downloadButton.addEventListener('click', async (event) => {
        event.preventDefault();  // 阻止默认行为，避免直接跳转

        // 调用文件系统选择保存路径并保存文件
        try {
            const fileHandle = await window.showSaveFilePicker({
                suggestedName: "model.stl",  // 默认文件名
                types: [{
                    description: 'STL Files',
                    accept: {'application/stl': ['.stl']}
                }]
            });

            // stl文件的内容
            const response = await fetch(stlFileUrl);
            const fileBlob = await response.blob();

            // 创建文件写入流
            const writableStream = await fileHandle.createWritable();
            await writableStream.write(fileBlob);
            await writableStream.close();
            console.log('STL file has been saved successfully!');
        } catch (error) {
            console.error('Error saving the STL file:', error);
        }
    });    
    
    // 添加到新的 div 中
    downloadContainer.appendChild(downloadButton);

    console.log(`STL file is available at: ${stlFileUrl}`);
}


//将stl文件可视化
function stlToVis(event) {
    let file;
    if (event instanceof Blob && event.type === "application/stl") {
        file = event; // 直接使用 event 作为文件
    } else if (event.target.files[0]) {
        file = event.target.files[0]; // 按照原逻辑处理
    } else {
        console.error("No valid STL file provided.");
        return; // 如果都不符合，返回
    }
    if (file && (file.type == "application/stl" || file.name.endsWith(".stl"))) {
        const reader = new FileReader();
        reader.onload = function (e) {
            const loader = new STLLoader();
            const geometry = loader.parse(e.target.result); //加载stl文件内容
            console.log("Geometry loaded:", geometry);

            if (mesh) { //此部分为避免重复绘制
                scene.remove(mesh);
                if (edges) {
                    scene.remove(edges);
                }
            }

            if (geometry) {
                geometry.computeVertexNormals();

                const material = new THREE.MeshStandardMaterial({
                    color: 0x888888,
                    flatShading: true,
                    metalness: 0.5,
                    roughness: 0.5,
                    side: THREE.DoubleSide
                });
                mesh = new THREE.Mesh(geometry, material);
                scene.add(mesh);
                mesh.rotation.x = -Math.PI / 2;
                mesh.position.set(0, 0, 0);
                console.log("Mesh added to scene:", mesh);

                const edgesGeometry = new THREE.EdgesGeometry(geometry, 1); // 重新计算边界线
                const edgesMaterial = new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 2 });  // 黑色边界线
                
                edges = new THREE.LineSegments(edgesGeometry, edgesMaterial);
                
               
                edges.rotation.copy(mesh.rotation);   // 确保边界线的旋转、位置与模型一致。否则会导致边界线旋转而不贴合。
                edges.position.copy(mesh.position);
                
                scene.add(edges);
            } else {
                console.error("Failed to load geometry.");
            }
        };
        reader.readAsArrayBuffer(file);
    } else console.error("Not a valid STL file.");
}


// 更新控制
function animate() {
    requestAnimationFrame(animate);
    controls.update(); 
    renderer.render(scene, camera);
}

// 画布
window.addEventListener('resize', () => {
    const visualizationContainer = document.getElementById('visualization');
    camera.aspect = visualizationContainer.clientWidth / visualizationContainer.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(visualizationContainer.clientWidth, visualizationContainer.clientHeight);
});

init();
animate();