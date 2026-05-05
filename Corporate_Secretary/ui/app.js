document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('secretary-form');
    const generateBtn = document.getElementById('generate-btn');
    const btnText = document.querySelector('.btn-text');
    const loader = document.querySelector('.loader');
    const statusMsg = document.getElementById('status-message');

    function setupDropZone(dropZoneId, inputId, listId) {
        const dropZone = document.getElementById(dropZoneId);
        const input = document.getElementById(inputId);
        const list = document.getElementById(listId);

        dropZone.addEventListener('click', () => input.click());

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                updateFileList(input.files, list);
            }
        });

        input.addEventListener('change', () => {
            updateFileList(input.files, list);
        });
    }

    function updateFileList(files, listElement) {
        listElement.innerHTML = '';
        Array.from(files).forEach(file => {
            const div = document.createElement('div');
            div.textContent = file.name;
            listElement.appendChild(div);
        });
    }

    setupDropZone('master-drop-zone', 'master-files', 'master-file-list');
    setupDropZone('monthly-drop-zone', 'monthly-files', 'monthly-file-list');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        statusMsg.classList.add('hidden');
        statusMsg.className = 'hidden';
        btnText.textContent = 'Generating...';
        loader.classList.add('visible');
        generateBtn.disabled = true;

        const formData = new FormData(form);

        try {
            const response = await fetch('/generate_minutes', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                
                // Extract filename from Content-Disposition header if possible
                let filename = "Meeting_Minutes.docx";
                const disposition = response.headers.get('content-disposition');
                if (disposition && disposition.indexOf('filename=') !== -1) {
                    filename = disposition.split('filename=')[1].replace(/["']/g, '');
                }
                
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
                
                statusMsg.textContent = 'Minutes generated successfully!';
                statusMsg.className = 'success';
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'An error occurred during generation.');
            }
        } catch (error) {
            statusMsg.textContent = error.message;
            statusMsg.className = 'error';
        } finally {
            btnText.textContent = 'Generate Minutes';
            loader.classList.remove('visible');
            generateBtn.disabled = false;
            statusMsg.classList.remove('hidden');
        }
    });
});
