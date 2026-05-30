import axios from 'axios';

/**
 * Actuates a Workspace Blueprint on the Sentinel Bridge backend.
 * Synthesized for Phase 3 - Blueprint Actuation Transport Layer.
 * STRICT GUARDRAIL: Traps 502 and 422 errors and throws clear descriptive exceptions.
 * 
 * @param {Object} blueprintInput - Strict WorkspaceBlueprintInput object.
 * @returns {Promise<Object>} - Actuation result from backend.
 */
export const actuateWorkspaceBlueprint = async (blueprintInput) => {
  try {
    const response = await axios.post('/api/workspace/actuate', blueprintInput, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  } catch (error) {
    let errorMessage = 'Workspace actuation failed.';
    let detail = '';

    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;

      if (status === 422) {
        errorMessage = 'Validation Error (422): Blueprint payload does not strictly match the WorkspaceBlueprintInput schema.';
        detail = data.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : 'Unprocessable Entity';
      } else if (status === 502) {
        errorMessage = 'Gateway Fallback Error (502): The backend was unable to reach the downstream Google Slides service.';
        detail = data.detail || data.error || 'Bad Gateway';
      } else {
        errorMessage = `HTTP ${status}: ${data.detail || data.error || error.response.statusText}`;
        detail = JSON.stringify(data);
      }
    } else if (error.request) {
      errorMessage = 'Network Error: No response received from the backend actuator.';
      detail = error.message;
    } else {
      errorMessage = error.message;
    }

    const enhancedError = new Error(errorMessage);
    enhancedError.status = error.response ? error.response.status : null;
    enhancedError.detail = detail;
    throw enhancedError;
  }
};
