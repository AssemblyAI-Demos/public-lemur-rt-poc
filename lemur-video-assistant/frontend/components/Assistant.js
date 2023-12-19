import React, { useEffect, useState, useContext } from 'react';
import StreamIdContext from '@/contexts/StreamIdContext';

const Assistant = () => {
    const { streamId } = useContext(StreamIdContext);
    const [data, setData] = useState({
        areTheyQualified: '',
        currentCRM: '',
        enthusiasmLevel: '',
        numberOfUsers: '',
        salesWorkflowNotes: '',
        nextSteps: '',
        otherNotes: ''
    });
    const [editMode, setEditMode] = useState(false);

    useEffect(() => {
        const eventSource = new EventSource(`https://5fa1b8a8c9f0.ngrok.app/stream?streamid=${streamId}`, {
            withCredentials: true,
        });

        eventSource.onmessage = (event) => {
            console.log(event.data);
            const eventData = JSON.parse(event.data);
            const lemurResponse = eventData.lemur_response;
            console.log(lemurResponse)
            // Check if lemurResponse has content other than an empty space
            if (lemurResponse && lemurResponse.trim() !== '') {
                const parsedData = parseLemurResponse(lemurResponse);
                console.log(parsedData);
                setData(parsedData);
            }
        }

        return () => eventSource.close();
    }, [streamId]);

    const cleanResponse = (response) => {
        // Remove all characters before the first occurrence of '##'
        return response.replace(/^[\s\S]*?(?=##)/, '');
    };


    const parseLemurResponse = (response) => {
        const normalizedResponse = response.replace(/\\n/g, '\n');
    
        const sections = normalizedResponse.split('##').slice(1); // Split the response into sections
        const parsedData = {};
    
        // Define a mapping from the headings to your state keys
        const keyMapping = {
            'areTheyQualified?': 'areTheyQualified',
            'what is their current crm?': 'currentCRM',
            'general enthusiasm level for our product/company': 'enthusiasmLevel',
            'numberOfUsers': 'numberOfUsers',
            'sales workflow notes': 'salesWorkflowNotes',
            'nextSteps': 'nextSteps',
            'otherNotes': 'otherNotes'
        };
    
        sections.forEach(section => {
            let [heading, ...contentLines] = section.trim().split('\n');
            heading = heading.trim().toLowerCase().replace(/\?/g, ''); // Remove question marks
    
            // Map the heading to the key defined in the state if available
            const stateKey = keyMapping[heading] || heading;
    
            // Convert the heading into camelCase to match the state keys if not found in mapping
            const key = stateKey || heading.replace(/(?:^\w|[A-Z]|\b\w|\s+)/g, (word, index) =>
                index === 0 ? word.toLowerCase() : word.toUpperCase()).replace(/\s/g, '');
    
            const value = contentLines.map(line => line.trim().replace(/^-\s*/, '')).join(' ');
    
            parsedData[key] = value;
        });
    
        return parsedData;
    };
    

    const handleChange = (e) => {
        const { name, value } = e.target;
        setData(prevData => ({
            ...prevData,
            [name]: value
        }));
    };

    const handleEditToggle = () => {
        setEditMode(!editMode);
    };

    return (
        <div className="flex flex-col h-7/8 text-custom-white bg-custom-off-blue rounded-md">
            <h2 className="text-xl p-2 font-bold mb-2">LeMUR Assistant</h2>
            {/* <button onClick={handleEditToggle}>
                {editMode ? 'Save' : 'Edit'}
            </button> */}
            <div className="flex-grow overflow-auto bg-gray-200 p-2 rounded-sm shadow-inner text-black">
                {editMode ? (
                    <>
                        <label >Are they qualified?</label>
                        <textarea name="qualified" value={data['are they qualified']} onChange={handleChange} />
                        <label>What is their current CRM?</label>
                        <input type="text" name="currentCRM" value={data['what is their current crm']} onChange={handleChange} />
                        
                        <label>General Enthusiasm Level For Our Product/Company</label>
                        <input type="dropdown" name="enthusiasmLevel" value={data.enthusiasmLevel} onChange={handleChange} />

                        <label>How did they hear about us?</label>
                        <input type="dropdown" name="leadSource" value={data['how did they hear about us?']} onChange={handleChange} />

                        <label>Did they watch the demo video?</label>
                        <input type="dropdown" name="watchedDemo" value={data['did they watch the demo video']} onChange={handleChange} />
                        
                        <label>How many users/employees do they have?</label>
                        <input type="number" name="numberOfUsers" value={data['how many users/employees do they have']} onChange={handleChange} />
                        
                        <label>Top Sales Challenges</label>
                        <textarea name="topSalesChallenges" value={data['top sales challenges']} onChange={handleChange} />

                        <label>Sales Workflow Notes</label>
                        <textarea name="salesWorkflowNotes" value={data.salesWorkflowNotes} onChange={handleChange} />
                        
                        <label>Next Steps</label>
                        <textarea name="nextSteps" value={data['next steps']} onChange={handleChange} />
                        
                        <label>Other Notes</label>
                        <textarea name="otherNotes" value={data['other notes']} onChange={handleChange} />
                    </>
                ) : (
                    <>
                        <p className='p-2'><strong>Are they qualified?</strong> {data['are they qualified']}</p>
                        <p className='p-2'><strong>What is their current CRM?</strong> {data['what is their current crm']}</p>
                        <p className='p-2'><strong>General Enthusiasm Level For Our Product/Company:</strong> {data.enthusiasmLevel}</p>
                        <p className='p-2'><strong>How did they hear about us?</strong> {data['how did they hear about us']}</p>
                        <p className='p-2'><strong>Did they watch the demo video?</strong> {data['did they watch the demo video']}</p>
                        <p className='p-2'><strong>How many users/employees do they have?</strong> {data['how many users/employees do they have']}</p>
                        <p className='p-2'><strong>Top Sales Challenges:</strong> {data['top sales challenges']}</p>
                        <p className='p-2'><strong>Sales Workflow Notes:</strong> {data.salesWorkflowNotes}</p>
                        <p className='p-2'><strong>Next Steps:</strong> {data['next steps']}</p>
                        <p className='p-2'><strong>Other Notes:</strong> {data['other notes']}</p>
                    </>
                )}
            </div>
        </div>
    )
}

export default Assistant;
