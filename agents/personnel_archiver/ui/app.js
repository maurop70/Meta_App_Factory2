document.addEventListener('DOMContentLoaded', () => {
    const runBtn = document.getElementById('generate-btn');
    const btnText = runBtn.querySelector('.btn-text');
    const loader = runBtn.querySelector('.loader');
    const statusMessage = document.getElementById('status-message');
    const logOutput = document.getElementById('log-output');

    runBtn.addEventListener('click', async () => {
        // UI Loading State
        runBtn.disabled = true;
        btnText.textContent = 'Running...';
        loader.classList.remove('hidden');
        statusMessage.classList.add('hidden');
        logOutput.classList.add('hidden');
        statusMessage.className = ''; // Reset classes

        try {
            const response = await fetch('http://localhost:5000/api/archiver/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (response.ok) {
                statusMessage.textContent = 'Archiving Completed Successfully!';
                statusMessage.classList.add('success');
                
                if (data.output) {
                    logOutput.textContent = data.output;
                    logOutput.classList.remove('hidden');
                }
            } else {
                throw new Error(data.error || 'Failed to run archiver');
            }
        } catch (error) {
            console.error('Archiver Error:', error);
            statusMessage.textContent = `Error: ${error.message}`;
            statusMessage.classList.add('error');
        } finally {
            // Reset UI State
            statusMessage.classList.remove('hidden');
            runBtn.disabled = false;
            btnText.textContent = 'Run Archiver';
            loader.classList.add('hidden');
        }
    });
});
