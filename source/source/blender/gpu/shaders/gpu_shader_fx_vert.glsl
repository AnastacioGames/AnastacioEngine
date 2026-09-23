out vec4 uvcoord;

//very simple shader for full screen FX, just pass values on

void main()
{
	uvcoord = gl_MultiTexCoord0;
	gl_Position = gl_Vertex;
}
