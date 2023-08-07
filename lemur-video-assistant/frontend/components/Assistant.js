import React, { useEffect, useState, useContext } from 'react';
import StreamIdContext from '@/contexts/StreamIdContext';

const Assistant = () => {
    const [lemurResults, setLemurResults] = useState(null)
    const { streamId } = useContext(StreamIdContext);

    useEffect(() => {
        console.log(streamId)
        //create new event source
        const eventSource = new EventSource(`https://4bdf604b79e1.ngrok.app/stream?streamid=${streamId}`, {
            withCredentials: true,
        });

        eventSource.onmessage = (event) => {
            console.log(event.data);
            const data = JSON.parse(event.data)
            console.log(data);
            const paragraphs = Object.values(data).map(obj => {
                const paragraph = Object.values(obj)[0];
                return typeof paragraph === 'string' ? paragraph.split('•') : [];
            });
            
            console.log("Paragraphs: ", paragraphs);
            setLemurResults(paragraphs);
        }
    
        return () => eventSource.close();
      }, [streamId]);

    return (

        <div className="flex flex-col h-3/4 text-custom-white bg-custom-off-blue rounded-md">
            <h2 className="text-xl p-2 font-bold mb-2">LeMUR Assistant</h2>
            <div className="flex-grow overflow-auto bg-gray-200 p-2 rounded-sm shadow-inner text-black">
                {lemurResults === null
                    ? "Waiting for responses..."
                    : lemurResults.map((para, paraIndex) => (
                        <div key={paraIndex}>
                            {para.map((bulletPoint, bpIndex) => bulletPoint.trim() !== "" && <li key={bpIndex} className="text-sm">{bulletPoint}</li>)}
                        </div>
                    ))
                }
            </div>
            </div>
    )
}

export default Assistant;


